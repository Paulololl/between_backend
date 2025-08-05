import json
import os
from datetime import timedelta

from django.core.cache import cache
from django.db import transaction
from jwt.exceptions import ExpiredSignatureError, DecodeError, InvalidTokenError
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError

from client_application.serializers import ApplicationSerializer, ListApplicationSerializer
from user_account.models import User, AuditLog
import googlemaps
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from googlemaps import Client
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
import requests
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken

from between_ims import settings
from cea_management.models import Program, Department, School
from client_matching.models import HardSkillsTagList, SoftSkillsTagList
from .models import Applicant, User, Company, CareerEmplacementAdmin, OJTCoordinator

from cea_management.serializers import ProgramSerializer

from django.core.exceptions import ValidationError

from .utils import validate_file_size

load_dotenv(dotenv_path=os.path.join('wwwroot', '.env'))


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
# def get_coordinates(location):
#     geolocator = Nominatim(user_agent="abcd")
#     try:
#         location = geolocator.geocode(location)
#         if location:
#             return {'lat': location.latitude, 'lng': location.longitude}
#         else:
#             print('error: Unable to get the location')
#             return None
#     except Exception as e:
#         print(f'Exception: {e}')
#         return None


# Google Maps
def get_google_coordinates(location):
    gmaps = googlemaps.Client(key=os.getenv('GOOGLEMAPS_API_KEY'))

    try:
        location = gmaps.geocode(location)
        if location:
            latitude = location[0]['geometry']['location']['lat']
            longitude = location[0]['geometry']['location']['lng']
            return latitude, longitude
        else:
            serializers.ValidationError({'Error:' 'Unable to get the location'})
            return None
    except Exception as e:
        print(f'Exception: {e}')
        return None


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
            'mobile_number'
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

        # if address:
        #     coordinates = get_coordinates(address)
        #     if coordinates:
        #         lat = coordinates['lat']
        #         lng = coordinates['lng']
        #         attrs['latitude'] = lat
        #         attrs['longitude'] = lng
        #
        #     else:
        #         raise serializers.ValidationError({'address': 'Unable to retrieve coordinates'})

        if address:
            coordinates = get_google_coordinates(address)
            if coordinates:
                lat, lng = coordinates
                attrs['latitude'] = lat
                attrs['longitude'] = lng

            else:
                raise serializers.ValidationError({'address': 'Unable to retrieve coordinates'})

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        email = validated_data.pop('applicant_email')
        password = validated_data.pop('password')
        validated_data.pop('confirm_password')
        hard_skills_string = validated_data.pop('hard_skills')
        soft_skills_string = validated_data.pop('soft_skills')

        resume = validated_data.get('resume')
        enrollment_record = validated_data.get('enrollment_record')

        if resume:
            try:
                validate_file_size(resume)
            except serializers.ValidationError as e:
                raise serializers.ValidationError({'resume': e.detail})

        if enrollment_record:
            try:
                validate_file_size(enrollment_record)
            except serializers.ValidationError as e:
                raise serializers.ValidationError({'enrollment_record': e.detail})

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'applicant_email': 'This email is already in use.'})

        try:
            user = User.objects.create_user(
                email=email,
                password=password,
                user_role='applicant',
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

        except Exception:
            raise serializers.ValidationError({'non_field_errors': 'Something went wrong with the server.'})


class CompanyRegisterSerializer(serializers.ModelSerializer):
    company_email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    company_website_url = serializers.CharField(allow_null=True, allow_blank=True)

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

        # if address:
        #     coordinates = get_coordinates(address)
        #     if coordinates:
        #         lat, lng = coordinates
        #         attrs['coordinates'] = {'lat': lat, 'lng': lng}
        #     else:
        #         raise serializers.ValidationError({'company_address': 'Unable to retrieve coordinates'})

        # if address:
        #     coordinates = get_google_coordinates(address)
        #     if coordinates:
        #         lat, lng = coordinates
        #         attrs['latitude'] = lat
        #         attrs['longitude'] = lng
        #
        #     else:
        #         raise serializers.ValidationError({'address': 'Unable to retrieve coordinates'})

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        email = validated_data.pop('company_email')
        password = validated_data.pop('password')
        validated_data.pop('confirm_password')
        coordinates = validated_data.pop('coordinates', None),
        profile_picture = validated_data.get('profile_picture')
        background_image = validated_data.get('background_image')

        if profile_picture:
            try:
                validate_file_size(profile_picture)
            except serializers.ValidationError as e:
                raise serializers.ValidationError({'profile_picture': e.detail})

        if background_image:
            try:
                validate_file_size(background_image)
            except serializers.ValidationError as e:
                raise serializers.ValidationError({'background_image': e.detail})

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'company_email': 'This email is already in use.'})

        try:
            print("✅ VALIDATED DATA BEFORE CREATION:", validated_data)

            user = User.objects.create_user(
                email=email,
                password=password,
                user_role='company',
                date_joined=timezone.now(),
            )

            company = Company.objects.create(user=user, **validated_data)
            return company
        except Exception:
            raise serializers.ValidationError({'non_field_errors': 'Something went wrong with the server.'})


class CareerEmplacementAdminRegisterSerializer(serializers.ModelSerializer):
    cea_email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = CareerEmplacementAdmin
        fields = ['cea_email', 'password', 'confirm_password', 'school']

    def validate_password(self, value):
        user_data = {
            'email': self.initial_data.get('cea_email', ''),
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

    @transaction.atomic
    def create(self, validated_data):
        email = validated_data.pop('cea_email')
        password = validated_data.pop('password')
        validated_data.pop('confirm_password')

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'cea_email': 'This email is already in use.'})

        user = User.objects.create_user(
            email=email,
            password=password,
            user_role='cea',
            status='Active'
        )

        cea = CareerEmplacementAdmin.objects.create(user=user, **validated_data)
        return cea


class OJTCoordinatorDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = OJTCoordinator
        fields = ['program_logo', 'signature']

    def update(self, instance, validated_data):
        new_logo = validated_data.get('program_logo')
        new_signature = validated_data.get('signature')

        if new_logo:
            try:
                validate_file_size(new_logo)
            except serializers.ValidationError as e:
                raise serializers.ValidationError({'program_logo': e.detail})
            if instance.program_logo and instance.program_logo != new_logo:
                instance.program_logo.delete(save=False)

        if new_signature:
            try:
                validate_file_size(new_signature)
            except serializers.ValidationError as e:
                raise serializers.ValidationError({'signature': e.detail})
            if instance.signature and instance.signature != new_signature:
                instance.signature.delete(save=False)

        return super().update(instance, validated_data)


class OJTCoordinatorRegisterSerializer(serializers.ModelSerializer):
    ojtcoordinator_email = serializers.EmailField(write_only=True)
    middle_initial = serializers.CharField(write_only=True, required=False, allow_blank=True, default='')
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    status = serializers.CharField(source='user.status', default='Active')

    program = serializers.PrimaryKeyRelatedField(queryset=Program.objects.all(), required=False, allow_null=True)
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), required=True, allow_null=False)

    class Meta:
        model = OJTCoordinator
        fields = [
            'ojtcoordinator_email'
            , 'first_name'
            , 'last_name'
            , 'middle_initial'
            , 'password'
            , 'confirm_password'
            , 'program'
            , 'department'
            , 'status'
            , 'program_logo'
        ]

    def validate_password(self, value):
        user_data = {
            'email': self.initial_data.get('ojtcoordinator_email', ''),
        }
        user = User(**user_data)

        try:
            validate_password(value, user=user)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

    def validate_ojtcoordinator_email(self, email):
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            if existing_user.status == 'Deleted':
                raise ValidationError(
                    'Re-activation of OJT Coordinator account is currently not allowed. Please contact the'
                    ' administrator for assistance.'
                )
            else:
                raise ValidationError('A user with this email already exists.')
        return email

    def validate_program(self, program):
        if program and program.department.school != self.context.get('school'):
            raise ValidationError('The selected program does not belong to your school.')

        if not program:
            return program

        existing = OJTCoordinator.objects.filter(
            program=program,
            user__status__in=['Active', 'Inactive']
        )
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise serializers.ValidationError('The selected program already has an assigned OJT Coordinator.')

        return program

    def validate_department(self, department):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError('Request context is missing.')

        try:
            cea = CareerEmplacementAdmin.objects.get(user=request.user)
        except CareerEmplacementAdmin.DoesNotExist:
            raise serializers.ValidationError('CEA school context is missing or invalid.')

        if not cea.school:
            raise serializers.ValidationError('CEA does not have an associated school.')

        if department.school != cea.school:
            raise serializers.ValidationError('The selected department does not belong to your school.')

        return department

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})

        program = attrs.get('program')
        department = attrs.get('department')
        if program and department and program.department_id != department.department_id:
            raise serializers.ValidationError({'program': 'The selected program does not belong to the selected department.'})

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        email = validated_data.pop('ojtcoordinator_email')
        password = validated_data.pop('password')
        validated_data.pop('confirm_password')

        user = User.objects.create_user(
            email=email,
            password=password,
            user_role='coordinator',
            status='Active',
        )
        validated_data['user'] = user

        ojt_coordinator = OJTCoordinator.objects.create(**validated_data)

        return ojt_coordinator


# inherit from ojt coordinator register serializer
class EditOJTCoordinatorSerializer(OJTCoordinatorRegisterSerializer):
    ojtcoordinator_email = serializers.EmailField(required=False)
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    middle_initial = serializers.CharField(write_only=True, required=False, allow_blank=True, default='')
    password = serializers.CharField(write_only=True, required=False)
    confirm_password = serializers.CharField(write_only=True, required=False)
    status = serializers.CharField(source='user.status', required=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        new_status = attrs.get('user', {}).get('status')
        instance = self.instance
        if instance.user.status == 'Deleted' and new_status != 'Deleted':
            raise serializers.ValidationError(
                'Re-activation of OJT Coordinator account is currently not allowed. Please contact the administrator for assistance.'
            )

        return attrs

    def validate_program(self, program):
        if not program or (self.instance and self.instance.program_id == program.program_id):
            return program

        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError('Request context is missing.')

        try:
            cea = CareerEmplacementAdmin.objects.get(user=request.user)
        except CareerEmplacementAdmin.DoesNotExist:
            raise serializers.ValidationError('CEA school context is missing or invalid.')

        if not cea.school:
            raise serializers.ValidationError('CEA does not have an associated school.')

        if str(program.department.school.school_id) != str(cea.school.school_id):
            raise serializers.ValidationError('The selected program does not belong to your school.')

        existing = OJTCoordinator.objects.filter(
            program=program,
            user__status__in=['Active', 'Inactive']
        )
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise serializers.ValidationError('The selected program already has an assigned OJT Coordinator.')

        return program

    def validate_department(self, department):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError('Request context is missing.')

        try:
            cea = CareerEmplacementAdmin.objects.get(user=request.user)
        except CareerEmplacementAdmin.DoesNotExist:
            raise serializers.ValidationError('CEA school context is missing or invalid.')

        if not cea.school:
            raise serializers.ValidationError('CEA does not have an associated school.')

        if department.school != cea.school:
            raise serializers.ValidationError('The selected department does not belong to your school.')

        return department

    def validate_ojtcoordinator_email(self, email):
        if self.instance and self.instance.user.email == email:
            return email

        assigned_coordinator = OJTCoordinator.objects.filter(user__email=email).exclude(user__status='Deleted')

        if self.instance:
            assigned_coordinator = assigned_coordinator.exclude(pk=self.instance.pk)

        if assigned_coordinator.exists():
            raise serializers.ValidationError('This email is currently in use by another OJT Coordinator.')

        return super().validate_ojtcoordinator_email(email)

    def update(self, instance, validated_data):
        email = validated_data.pop("ojtcoordinator_email", None)
        if email:
            instance.user.email = email

        password = validated_data.pop("password", None)
        if password:
            instance.user.set_password(password)

        user_data = validated_data.pop("user", {})
        if "status" in user_data:
            instance.user.status = user_data["status"]

        instance.user.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance


class GetOJTCoordinatorSerializer(serializers.ModelSerializer):
    program = ProgramSerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    status = serializers.CharField(source='user.status')

    class Meta:
        model = OJTCoordinator
        fields = [
            'user',
            'ojt_coordinator_id',
            'program',
            'department',
            'first_name',
            'last_name',
            'middle_initial',
            'email',
            'status',
            'program_logo',
            'signature',
            'endorsements_responded'
        ]


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
            raise serializers.ValidationError({'token': 'Invalid refresh token'})

        user_id = token.get('user_id')

        try:
            user = get_user_model().objects.get(user_id=user_id)
        except get_user_model().DoesNotExist:
            raise serializers.ValidationError({'user': 'User does not exist.'})

        data = super().validate(attrs)
        data['user_id'] = user.user_id
        data['user_role'] = user.user_role

        return data


class EmailLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    status = serializers.CharField(read_only=True, required=False)

    def validate_email(self, value):
        try:
            user = User.objects.get(
                email=value)

        except User.DoesNotExist:
            raise serializers.ValidationError('Email not found. Please try again.')

        if user.status == 'Inactive':
            raise serializers.ValidationError('Email is Inactive.')

        if user.status == 'Deleted':
            raise serializers.ValidationError('Email not found. Please try again.')

        if user.status == 'Suspended':
            raise serializers.ValidationError('Email is Suspended. Please try again.')

        self.user = user
        return value


class SchoolEmailCheckSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    school_id = serializers.UUIDField(required=True)

    def validate(self, data):
        email = data.get('email')
        school_id = data.get('school_id')

        abstract_api_key = os.getenv('ABSTRACT_API_KEY')
        url = f"https://emailvalidation.abstractapi.com/v1/"
        params = {'api_key': abstract_api_key, 'email': email}

        response = requests.get(url, params=params)

        if response.status_code != 200:
            raise serializers.ValidationError({'email': 'Failed to validate email with external service.'})

        data_api = response.json()

        errors = []

        try:
            if data_api.get('deliverability') != 'DELIVERABLE':
                errors.append('Email is not deliverable.')

            if float(data_api.get('quality_score', 0)) < 0.80:
                errors.append('Email may not exist.')

            if not data_api.get('is_valid_format', {}).get('value', False):
                errors.append('Email format is invalid.')

            if data_api.get('is_free_email', {}).get('value', True):
                errors.append('Email is not an institutional email.')

            if data_api.get('is_disposable_email', {}).get('value', True):
                errors.append('Disposable email addresses are not allowed.')

            if not data_api.get('is_smtp_valid', {}).get('value', False):
                errors.append('smtp is invalid.')

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
    school = serializers.CharField(source='school.school_name', allow_blank=True, allow_null=True)
    department = serializers.CharField(source='department.department_name', allow_blank=True, allow_null=True)
    program = serializers.CharField(source='program.program_name', allow_blank=True, allow_null=True)
    applications = ListApplicationSerializer(many=True, read_only=True)
    application_status = serializers.SerializerMethodField()

    class Meta:
        model = Applicant
        fields = ['user', 'email', 'school', 'department', 'program', 'first_name', 'last_name',
                  'middle_initial', 'address', 'hard_skills', 'soft_skills', 'in_practicum',
                  'preferred_modality', 'academic_program', 'quick_introduction',
                  'resume', 'enrollment_record', 'verified_at', 'mobile_number', 'application_status', 'applications']

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

    def get_application_status(self, obj):
        if obj.applications.filter(status='Accepted').exists():
            return "Accepted"
        return "Pending"


class GetCompanySerializer(serializers.ModelSerializer):
    verified_at = serializers.DateTimeField(source='user.verified_at')
    email = serializers.EmailField(source='user.email')

    class Meta:
        model = Company
        fields = ['user', 'email', 'company_name', 'company_address', 'company_information', 'business_nature',
                  'company_website_url', 'linkedin_url', 'facebook_url', 'instagram_url', 'x_url',
                  'other_url', 'background_image', 'profile_picture', 'verified_at']


class SendEmailVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    expiration_time = serializers.DateTimeField(required=False)

    def validate_email(self, value):
        from user_account.models import User

        try:
            user = User.objects.get(email=value)

        except User.DoesNotExist:
            raise serializers.ValidationError('User with this email does not exist.')

        if user.status == 'Active':
            raise serializers.ValidationError('This email is already active.')

        if user.status == 'Inactive':
            raise serializers.ValidationError('This email is inactive.')

        if user.status == 'Deleted':
            raise serializers.ValidationError('User with this email does not exist.')

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

        # verification_url = f'https://localhost:8000/api/user_account/verify-email/{uid}/{token}/'

        verification_url = f'https://between-backend.up.railway.app/api/user_account/verify-email/{uid}/{token}/'

        subject = 'Verify your email'

        if hasattr(user, 'applicant'):
            display_name = f"{user.applicant.first_name} {user.applicant.last_name}"

        elif hasattr(user, 'company'):
            display_name = f"{user.company.company_name}"

        else:
            display_name = user.email

        message = (f'Hi {display_name},\n\n'
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


class SendForgotPasswordLinkSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError({'user': 'User with this email does not exist.'})

        self.user = user
        return value

    def send_password_reset_email(self):
        user = self.user
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        expiration_time = timezone.now() + timedelta(minutes=15)

        cache.set(f"reset_token_{user.pk}", token, timeout=900)
        cache.set(f"reset_expiration_{user.pk}", expiration_time, timeout=900)

        # reset_url = f'https://localhost:5173/reset-password?uid={uid}&token={token}'

        reset_url = f'https://between-project-web.vercel.app/reset-password?uid={uid}&token={token}'

        subject = "Between IMS forgot credentials"

        message = (f'Hi {user.email},\n\n'
                   f'Please change your credentials by clicking the link below:'
                   f'\n\n{reset_url}\n\nNote: This link will expire after 15 minutes.'
                   f'\n\nThank you!')

        send_mail(
            subject=subject,
            message=message,
            from_email='Between_IMS <no-reply.between.internships@gmail.com>',
            recipient_list=[user.email],
            fail_silently=False,
        )

    def create(self, validated_data):
        self.send_password_reset_email()
        return {'status': 'Credential change email sent successfully.'}


class ResetPasswordSerializer(serializers.Serializer):
    uidb64 = serializers.CharField()
    token = serializers.CharField()
    email = serializers.EmailField()
    new_password = serializers.CharField(write_only=True)
    confirm_new_password = serializers.CharField(write_only=True)

    def validate(self, data):
        uidb64 = data.get('uidb64')
        token = data.get('token')
        email = data.get('email')
        new_password = data.get('new_password')
        confirm_new_password = data.get('confirm_new_password')

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid, email=email)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({'uidb64': 'Invalid uid.'})

        stored_token = cache.get(f"reset_token_{user.pk}")
        expiration_time = cache.get(f"reset_expiration_{user.pk}")

        if not email:
            raise serializers.ValidationError({'email': 'Invalid email'})

        if not stored_token or token != stored_token:
            raise serializers.ValidationError({'token': 'Invalid or expired token.'})

        if expiration_time and expiration_time < timezone.now():
            raise serializers.ValidationError({'token': 'Token has expired.'})

        if user.check_password(new_password):
            raise serializers.ValidationError({'new_password': 'Please enter a new password.'})

        if new_password != confirm_new_password:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        try:
            validate_password(new_password)
        except ValidationError as e:
            raise serializers.ValidationError({'new_password': e.messages})

        self.user = user
        return data

    def save(self):
        user = self.user
        user.set_password(self.validated_data['new_password'])
        user.save()

        cache.delete(f"reset_token_{user.pk}")
        cache.delete(f"reset_expiration_{user.pk}")

        return user


class DeleteAccountSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        confirm_password = data.get('confirm_password')

        if password != confirm_password:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})

        user = self.context['request'].user

        if user.email.lower() != email.lower():
            raise serializers.ValidationError({'email': 'Invalid email'})

        if not user.check_password(password):
            raise serializers.ValidationError({'password': 'Invalid Password'})

        self.user = user
        return data

    def save(self):
        user = self.user
        user.status = 'Deleted'
        user.save()

        return user


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_new_password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = self.context['request'].user
        old_password = data.get('old_password')
        new_password = data.get('new_password')
        confirm_new_password = data.get('confirm_new_password')

        if not user.check_password(old_password):
            raise serializers.ValidationError({'old_password': 'Old password is incorrect.'})

        if user.check_password(new_password):
            raise serializers.ValidationError({'new_password': 'New password cannot be the same as the old password.'})

        if new_password != confirm_new_password:
            raise serializers.ValidationError({'confirm_new_password': 'Passwords do not match.'})

        try:
            validate_password(new_password, user)
        except ValidationError as e:
            raise serializers.ValidationError({'new_password': e.messages})

        return data

    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class EditCompanySerializer(serializers.ModelSerializer):
    company_website_url = serializers.CharField(allow_blank=True, allow_null=True)
    linkedin_url = serializers.CharField(allow_blank=True, allow_null=True)
    facebook_url = serializers.CharField(allow_blank=True, allow_null=True)
    instagram_url = serializers.CharField(allow_blank=True, allow_null=True)
    x_url = serializers.CharField(allow_blank=True, allow_null=True)
    other_url = serializers.CharField(allow_blank=True, allow_null=True)

    class Meta:
        model = Company
        fields = [
            'company_name',
            'company_address',
            'company_information',
            'business_nature',
            'company_website_url',
            'linkedin_url',
            'facebook_url',
            'instagram_url',
            'x_url',
            'other_url',
            'background_image',
            'profile_picture',
        ]

    def validate(self, attrs):

        address = attrs.get('company_address')

        if address is None:
            raise serializers.ValidationError({'company_address': 'This field is required.'})

        if len(address) < 15:
            raise serializers.ValidationError({'company_address': 'Address must be at least 15 characters.'})

        # coordinates = get_coordinates(address)
        # if coordinates:
        #     lat, lng = coordinates
        #     attrs['coordinates'] = {'lat': lat, 'lng': lng}
        # else:
        #     raise serializers.ValidationError({'company_address': 'Unable to retrieve coordinates'})
        #
        # coordinates = get_google_coordinates(address)
        # if coordinates:
        #     lat, lng = coordinates
        #     attrs['latitude'] = lat
        #     attrs['longitude'] = lng
        #
        # else:
        #     raise serializers.ValidationError({'address': 'Unable to retrieve coordinates'})

        return attrs

    def update(self, instance, validated_data):

        new_background_image = validated_data.get('background_image')
        if new_background_image:
            try:
                validate_file_size(new_background_image)
            except serializers.ValidationError as e:
                raise serializers.ValidationError({'background_image': e.detail})
            if instance.background_image and instance.background_image != new_background_image:
                instance.background_image.delete(save=False)

        new_profile = validated_data.get('profile_picture')
        if new_profile:
            try:
                validate_file_size(new_profile)
            except serializers.ValidationError as e:
                raise serializers.ValidationError({'profile_picture': e.detail})
            if instance.profile_picture and instance.profile_picture != new_profile:
                instance.profile_picture.delete(save=False)

        for attr, value in validated_data.items():
            if attr == 'coordinates':
                instance.latitude = value['lat']
                instance.longitude = value['lng']
            else:
                setattr(instance, attr, value)

        instance.save()
        return instance


class EditApplicantSerializer(serializers.ModelSerializer):
    hard_skills = serializers.CharField(write_only=True, required=False)
    soft_skills = serializers.CharField(write_only=True, required=False)
    displayed_hard_skills = serializers.SerializerMethodField()
    displayed_soft_skills = serializers.SerializerMethodField()

    class Meta:
        model = Applicant
        fields = [
            'first_name',
            'last_name',
            'middle_initial',
            'address',
            'hard_skills',
            'soft_skills',
            'displayed_hard_skills',
            'displayed_soft_skills',
            'resume',
            'enrollment_record',
            'quick_introduction',
            'preferred_modality',
            'mobile_number'
        ]

    def get_displayed_hard_skills(self, obj):
        return [
            {"id": skill.lightcast_identifier, "name": skill.name}
            for skill in obj.hard_skills.all()
        ]

    def get_displayed_soft_skills(self, obj):
        return [
            {"id": skill.lightcast_identifier, "name": skill.name}
            for skill in obj.soft_skills.all()
        ]

    def validate(self, attrs):
        address = attrs.get('address')

        if address is None:
            raise serializers.ValidationError({'address': 'This field is required.'})

        if len(address) < 15:
            raise serializers.ValidationError({'address': 'Address must be at least 15 characters.'})

        # coordinates = get_coordinates(address)
        # if coordinates:
        #     lat = coordinates['lat']
        #     lng = coordinates['lng']
        #     attrs['latitude'] = lat
        #     attrs['longitude'] = lng
        #
        # else:
        #     raise serializers.ValidationError({'address': 'Unable to retrieve coordinates'})

        coordinates = get_google_coordinates(address)
        if coordinates:
            lat, lng = coordinates
            attrs['latitude'] = lat
            attrs['longitude'] = lng

        else:
            raise serializers.ValidationError({'address': 'Unable to retrieve coordinates'})

        for field in ['hard_skills', 'soft_skills']:
            value = attrs.get(field)
            if value:
                try:
                    parsed = json.loads(value)
                    if not isinstance(parsed, list):
                        raise serializers.ValidationError({field: 'Must be a list.'})
                except json.JSONDecodeError:
                    raise serializers.ValidationError({field: 'Invalid JSON format.'})

        return attrs

    def update(self, instance, validated_data):
        hard_skills_json = validated_data.pop('hard_skills', None)
        soft_skills_json = validated_data.pop('soft_skills', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if 'latitude' in validated_data:
            instance.latitude = validated_data['latitude']
        if 'longitude' in validated_data:
            instance.longitude = validated_data['longitude']

        instance.save()

        if hard_skills_json:
            try:
                parsed_hard_skills = json.loads(hard_skills_json)
                hard_skill_objs = []
                for item in parsed_hard_skills:
                    obj, _ = HardSkillsTagList.objects.get_or_create(
                        lightcast_identifier=item['id'],
                        defaults={'name': item['name']}
                    )
                    hard_skill_objs.append(obj)
                instance.hard_skills.set(hard_skill_objs)
            except Exception:
                raise serializers.ValidationError({'hard skills': 'error in parsing hard skills'})

        if soft_skills_json:
            try:
                parsed_soft_skills = json.loads(soft_skills_json)
                soft_skill_objs = []
                for item in parsed_soft_skills:
                    obj, _ = SoftSkillsTagList.objects.get_or_create(
                        lightcast_identifier=item['id'],
                        defaults={'name': item['name']}
                    )
                    soft_skill_objs.append(obj)
                instance.soft_skills.set(soft_skill_objs)
            except Exception:
                raise serializers.ValidationError({'soft skills': 'error in parsing soft skills'})
        return instance


class GetUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['email', 'verified_at', 'user_role', 'status']


class GetEmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['user_id', 'verified_at', 'user_role', 'status']


class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'user_email',
            'user_role',
            'action_type',
            'action',
            'model',
            'object_id',
            'object_repr',
            'timestamp',
            'details',
        ]



