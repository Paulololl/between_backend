import json

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import requests
from cea_management.models import Program, Department, School
from client_matching.models import HardSkillsTagList, SoftSkillsTagList
from .models import Applicant, User, Company, CareerEmplacementAdmin, OJTCoordinator
from django.core.exceptions import ValidationError


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
            'address', 'quick_introduction', 'resume', 'enrollment_record',
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

        if errors:
            raise serializers.ValidationError({'school info': errors})

        return attrs

    def create(self, validated_data):
        email = validated_data.pop('applicant_email')
        password = validated_data.pop('password')
        validated_data.pop('confirm_password')
        hard_skills_string = validated_data.pop('hard_skills')
        soft_skills_string = validated_data.pop('soft_skills')

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'applicant_email': 'This email is already in use.'})

        user = User.objects.create_user(
            email=email,
            password=password,
            user_role='APPLICANT',
        )

        applicant = Applicant.objects.create(
            user=user,
            **validated_data)

        if hard_skills_string:
            try:
                hard_skills_json = json.loads(hard_skills_string)
                hard_skills = []
                for skill in hard_skills_json:
                    skill_instance, created = HardSkillsTagList.objects.get_or_create(
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
                    skill_instance, created = SoftSkillsTagList.objects.get_or_create(
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
        return attrs

    def create(self, validated_data):
        email = validated_data.pop('company_email')
        password = validated_data.pop('password')
        validated_data.pop('confirm_password')

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'company_email': 'This email is already in use.'})

        user = User.objects.create_user(
            email=email,
            password=password,
            user_role='COMPANY',
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
            raise serializers.ValidationError('Email does not exist')

        credentials = {
            'email': email,
            'password': password,
        }

        user = authenticate(**credentials)

        if user is None:
            raise serializers.ValidationError('Invalid email or password')

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

    class Meta:
        model = Applicant
        fields = ['user', 'email', 'school', 'department', 'program', 'first_name', 'last_name',
                  'middle_initial', 'address', 'hard_skills', 'soft_skills', 'in_practicum',
                  'preferred_modality', 'academic_program', 'quick_introduction',
                  'resume', 'enrollment_record']

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
