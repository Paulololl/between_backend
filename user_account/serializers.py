from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from cea_management.models import Program, Department
from .models import Applicant, User, School


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = ['school_id', 'school_name']


class DepartmentSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.school_name', read_only=True)

    class Meta:
        model = Department
        fields = ('school_name', 'department_id', 'name')


class ProgramSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='department.school.school_name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = Program
        fields = ['school_name', 'department_name', 'program_id', 'name']


class ApplicantRegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True)
    middle_initial = serializers.CharField(write_only=True, required=False, allow_blank=True, default='')
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = Applicant
        fields = [
            'first_name', 'last_name', 'middle_initial',
            'email', 'school', 'password', 'confirm_password',
            'department', 'program', 'academic_program',
            'address', 'quick_introduction', 'resume', 'enrollment_record',
        ]

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        validated_data.pop('confirm_password')

        user = User.objects.create_user(
            email=email,
            password=password,
            user_role='APPLICANT',
        )

        applicant = Applicant.objects.create(user=user, **validated_data)
        return applicant
