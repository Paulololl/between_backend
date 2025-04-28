import json
import os
from datetime import timedelta

from django.core.cache import cache

from user_account.models import User
import googlemaps
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from googlemaps import Client
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
import requests
from rest_framework_simplejwt.tokens import RefreshToken

from between_ims import settings
from cea_management.models import Program, Department, School
from client_matching.models import HardSkillsTagList, SoftSkillsTagList
from .models import Applicant, User, Company, CareerEmplacementAdmin, OJTCoordinator
from django.core.exceptions import ValidationError

load_dotenv()


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = ['school_id', 'school_name']


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['department_id', 'department_name']


class ProgramNestedSerializer(serializers.ModelSerializer):
    program_id = serializers.PrimaryKeyRelatedField(read_only=True)
    program_name = serializers.CharField(read_only=True)

    class Meta:
        model = Program
        fields = ['program_id', 'program_name']


class DepartmentNestedSerializer(serializers.ModelSerializer):
    department_id = serializers.PrimaryKeyRelatedField(read_only=True)
    department_name = serializers.CharField(read_only=True)
    programs = ProgramNestedSerializer(many=True, read_only=True)

    class Meta:
        model = Department
        fields = ['department_id', 'department_name', 'programs']


class NestedSchoolDepartmentProgramSerializer(serializers.ModelSerializer):
    school_id = serializers.UUIDField(read_only=True)
    school_name = serializers.CharField(read_only=True)
    departments = DepartmentNestedSerializer(many=True, read_only=True)

    class Meta:
        model = School
        fields = ['school_id', 'school_name', 'departments']


# Geopy
def get_coordinates(location):
    geolocator = Nominatim(user_agent="abcd")
    try:
        location = geolocator.geocode(location)
        if location:
            return {'lat': location.latitude, 'lng': location.longitude}
        else:
            print('Error: Unable to get the location')
            return None
    except Exception as e:
        print(f'Exception: {e}')
        return None


# Google Maps
# def get_google_coordinates(location):
#     gmaps = googlemaps.Client(key=os.getenv('GOOGLEMAPS_API_KEY'))
#
#     try:
#         location = gmaps.geocode(location)  # type: ignore[attr-defined]
#         if location:
#             latitude = location[0]['geometry']['location']['lat']
#             longitude = location[0]['geometry']['location']['lng']
#             return latitude, longitude
#         else:
#             print('Error: Unable to get the location')
#             return None
#     except Exception as e:
#         print(f'Exception: {e}')
#         return None


class ApplicantRegisterSerializer(serializers.ModelSerializer):
    applicant_email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    middle_initial = serializers.CharField(write_only=True, required=False, allow_blank=True, default='')
    confirm_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    hard_skills = serializers.CharField(required=True)
    soft_skills = serializers.CharField(required=True)

    school = serializers.PrimaryKeyRelatedField(
        queryset=School.objects.all(), required=False, allow_null=True
    )
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), required=False, allow_null=True
    )
    program = serializers.PrimaryKeyRelatedField(
        queryset=Program.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Applicant
        fields = [
            'first_name', 'last_name', 'middle_initial',
            'applicant_email', 'school', 'password', 'confirm_password',
            'department', 'program', 'academic_program', 'hard_skills', 'soft_skills',
            'address', 'preferred_modality', 'quick_introduction', 'resume', 'enrollment_record',
        ]

    def validate_password(self, value):
        user_data = {
            'email': self.initial_data.get('applicant_email', ''),
        }
        user = User(**user_data)

        try:
            validate_password(value, user=user)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})

        email = attrs.get('applicant_email', '')
        errors = []

        if '.edu' not in email and not attrs.get('academic_program'):
            raise serializers.ValidationError({
                'academic_program': 'This field is required for non .edu emails.'
            })

        if '.edu' in email:
            required_fields = ['school', 'department', 'program']
            for field in required_fields:
                if not attrs.get(field):
                    raise (serializers.ValidationError
                           ({field: f'{field.capitalize()} is required for school (.edu) emails.'}))

            school = attrs.get('school')
            department = attrs.get('department')
            program = attrs.get('program')

            if department and school and department.school_id != school.school_id:
                errors.append('Selected department does not belong to the selected school.')

            if program and department and program.department_id != department.department_id:
                errors.append('Selected program does not belong to the selected department.')

        address = attrs.get('address')
        if len(address) < 15:
            raise serializers.ValidationError({'address': 'Address must be at least 15 characters.'})

        if address:
            coordinates = get_coordinates(address)
            if coordinates:
                lat, lng = coordinates
                attrs['coordinates'] = {'lat': lat, 'lng': lng}
            else:
                raise serializers.ValidationError({'address': 'Unable to retrieve coordinates'})

            if errors:
                raise serializers.ValidationError({'school info': errors})

        # if address:
        #     coordinates = get_google_coordinates(address)
        #     if coordinates:
        #         lat, lng = coordinates
        #         attrs['coordinates'] = {'lat': lat, 'lng': lng}
        #     else:
        #         raise serializers.ValidationError({'address': 'Unable to retrieve coordinates from Google Maps.'})
        #
        #     if errors:
        #         raise serializers.ValidationError({'school info': errors})

        return attrs

    def create(self, validated_data):
        email = validated_data.pop('applicant_email')
        password = validated_data.pop('password')
        validated_data.pop('confirm_password')
        hard_skills_string = validated_data.pop('hard_skills')
        soft_skills_string = validated_data.pop('soft_skills')
        coordinates = validated_data.pop('coordinates', None)

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'applicant_email': 'This email is already in use.'})

        user = User.objects.create_user(
            email=email,
            password=password,
            user_role='APPLICANT',
        )

        applicant = Applicant.objects.create(user=user, **validated_data)

        if hard_skills_string:
            try:
                hard_skills_json = json.loads(hard_skills_string)
                hard_skills = []
                for skill in hard_skills_json:
                    skill_instance, _ = HardSkillsTagList.objects.get_or_create(
                        lightcast_identifier=skill['id'],
                        defaults={'name': skill['name']}
                    )
                    hard_skills.append(skill_instance)
                applicant.hard_skills.set(hard_skills)
            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid format for hard_skills")

        if soft_skills_string:
            try:
                soft_skills_json = json.loads(soft_skills_string)
                soft_skills = []
                for skill in soft_skills_json:
                    skill_instance, _ = SoftSkillsTagList.objects.get_or_create(
                        lightcast_identifier=skill['id'],
                        defaults={'name': skill['name']}
                    )
                    soft_skills.append(skill_instance)
                applicant.soft_skills.set(soft_skills)
            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid format for soft_skills")

        return applicant


class CompanyRegisterSerializer(serializers.ModelSerializer):
    company_email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = Company
        fields = [
            'company_name', 'company_address', 'company_website_url', 'company_email',
            'password', 'confirm_password', 'company_information', 'business_nature',
            'profile_picture', 'background_image',
        ]

    def validate_password(self, value):
        user_data = {
            'email': self.initial_data.get('company_email', ''),
        }
        user = User(**user_data)

        try:
            validate_password(value, user=user)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})

        address = attrs.get('company_address')
        if len(address) < 15:
            raise serializers.ValidationError({'company_address': 'Address must be at least 15 characters.'})

        if address:
            coordinates = get_coordinates(address)
            if coordinates:
                lat, lng = coordinates
                attrs['coordinates'] = {'lat': lat, 'lng': lng}
            else:
                raise serializers.ValidationError({'company_address': 'Unable to retrieve coordinates'})

        # if address:
        #     coordinates = get_google_coordinates(address)
        #     if coordinates:
        #         lat, lng = coordinates
        #         attrs['coordinates'] = {'lat': lat, 'lng': lng}
        #     else:
        #         raise serializers.ValidationError({'address': 'Unable to retrieve coordinates from Google Maps.'})

        return attrs

    def create(self, validated_data):
        email = validated_data.pop('company_email')
        password = validated_data.pop('password')
        validated_data.pop('confirm_password')
        coordinates = validated_data.pop('coordinates', None),

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'company_email': 'This email is already in use.'})

        else:
            user = User.objects.create_user(
                email=email,
                password=password,
                user_role='COMPANY',
                date_joined=timezone.now(),
            )

            company = Company.objects.create(user=user, **validated_data)
            return company


class CareerEmplacementAdminRegisterSerializer(serializers.ModelSerializer):
    CEA_email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = CareerEmplacementAdmin
        fields = ['CEA_email', 'password', 'confirm_password', 'school']

    def validate_password(self, value):
        user_data = {
            'email': self.initial_data.get('CEA_email', ''),
        }
        user = User(**user_data)

        try:
            validate_password(value, user=user)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        email = validated_data.pop('CEA_email')
        password = validated_data.pop('password')
        validated_data.pop('confirm_password')

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'CEA_email': 'This email is already in use.'})

        user = User.objects.create_user(
            email=email,
            password=password,
            user_role='CEA',
        )

        cea = CareerEmplacementAdmin.objects.create(user=user, **validated_data)
        return cea


class OJTCoordinatorRegisterSerializer(serializers.ModelSerializer):
    OJTCoordinator_email = serializers.EmailField(write_only=True)
    middle_initial = serializers.CharField(write_only=True, required=False, allow_blank=True, default='')
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = OJTCoordinator
        fields = ['OJTCoordinator_email', 'first_name', 'last_name', 'middle_initial',
                  'password', 'confirm_password', 'program']

    def validate_password(self, value):
        user_data = {
            'email': self.initial_data.get('OJTCoordinator_email', ''),
        }
        user = User(**user_data)

        try:
            validate_password(value, user=user)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        email = validated_data.pop('OJTCoordinator_email')
        password = validated_data.pop('password')
        validated_data.pop('confirm_password')

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'OJTCoordinator_email': 'This email is already in use.'})

        user = User.objects.create_user(
            email=email,
            password=password,
            user_role='OJT_COORDINATOR',
        )

        ojt_coordinator = OJTCoordinator.objects.create(user=user, **validated_data)
        return ojt_coordinator


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        try:
            User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({'email': 'Email does not exist'})

        credentials = {
            'email': email,
            'password': password,
        }

        user = authenticate(**credentials)

        if user is None:
            raise serializers.ValidationError({'password': 'Invalid Password'})

        data = super().validate(attrs)
        data['user_id'] = user.user_id
        data['user_role'] = user.user_role
        return data


class MyTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        refresh = attrs.get('refresh')

        try:
            token = RefreshToken(refresh)
        except Exception as e:
            raise serializers.ValidationError({'Token': 'Invalid refresh token'})

        user_id = token.get('user_id')

        try:
            user = get_user_model().objects.get(user_id=user_id)
        except get_user_model().DoesNotExist:
            raise serializers.ValidationError({'User': 'User does not exist.'})

        data = super().validate(attrs)
        data['user_id'] = user.user_id
        data['user_role'] = user.user_role

        return data


class EmailLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise ValidationError('Email not found. Please try again.')
        return value


class SchoolEmailCheckSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    school_id = serializers.UUIDField(required=True)

    def validate(self, data):
        email = data.get('email')
        school_id = data.get('school_id')

        abstract_api_key = 'd0282e1316c0496d9b777e3bce3911b0'
        url = f"https://emailvalidation.abstractapi.com/v1/"
        params = {'api_key': abstract_api_key, 'email': email}

        response = requests.get(url, params=params)

        if response.status_code != 200:
            raise serializers.ValidationError('Failed to validate email with external service.')

        data_api = response.json()

        errors = []

        try:
            if data_api.get('deliverability') != 'DELIVERABLE':
                errors.append('Email is not deliverable.')

            if float(data_api.get('quality_score', 0)) < 0.90:
                errors.append('Email may not exist.')

            if not data_api.get('is_valid_format', {}).get('value', False):
                errors.append('Email format is invalid.')

            if data_api.get('is_free_email', {}).get('value', True):
                errors.append('Email is not an institutional email.')

            if data_api.get('is_disposable_email', {}).get('value', True):
                errors.append('Disposable email addresses are not allowed.')

            domain = '@' + email.split('@', 1)[-1].strip().lower()

            school = School.objects.get(school_id=school_id)
            if school.domain.lower() != domain:
                errors.append('Email domain does not match the selected school.')
        except School.DoesNotExist:
            errors.append('Selected school does not exist.')

        if errors:
            raise serializers.ValidationError({'email': errors})

        return data


class GetApplicantSerializer(serializers.ModelSerializer):
    hard_skills = serializers.SerializerMethodField()
    soft_skills = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email')
    verified_at = serializers.DateTimeField(source='user.verified_at')

    class Meta:
        model = Applicant
        fields = ['user', 'email', 'school', 'department', 'program', 'first_name', 'last_name',
                  'middle_initial', 'address', 'hard_skills', 'soft_skills', 'in_practicum',
                  'preferred_modality', 'academic_program', 'quick_introduction',
                  'resume', 'enrollment_record', 'verified_at']

    def get_hard_skills(self, obj):
        return [
            {"id": skill.lightcast_identifier, "name": skill.name}
            for skill in obj.hard_skills.all()
        ]

    def get_soft_skills(self, obj):
        return [
            {"id": skill.lightcast_identifier, "name": skill.name}
            for skill in obj.soft_skills.all()
        ]


class SendEmailVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    expiration_time = serializers.DateTimeField(required=False)

    def validate_email(self, value):
        from user_account.models import User
        try:
            user = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError({'User': 'User with this email does not exist.'})

        self.user = user
        return value

    def send_verification_email(self):
        user = self.user
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        expiration_time = timezone.now() + timedelta(minutes=15)
        user.save()

        cache.set(f"verification_token_{user.pk}", token, timeout=900)
        cache.set(f"verification_expiration_{user.pk}", expiration_time, timeout=900)

        verification_url = f'https://localhost:8000/api/user_account/verify-email/{uid}/{token}/'

        # first_name = user.applicant.first_name

        subject = 'Verify your email'

        message = (f'Hi {user.email},\n\n'
                   f'Please verify your email by clicking the link below:'
                   f'\n\n{verification_url}\n\nNote: This link will expire after 15 minutes.'
                   f'\n\nThank you!')

        send_mail(
            subject=subject,
            message=message,
            from_email='Between_IMS <no-reply.between.internships@gmail.com>',
            recipient_list=[user.email],
            fail_silently=False,
        )

    def create(self, validated_data):
        self.send_verification_email()
        return {'status': 'Verification email sent successfully.'}
