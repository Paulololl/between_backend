from rest_framework import serializers

from user_account.models import Company, CareerEmplacementAdmin, AuditLog
from .models import SchoolPartnershipList, Program, Department, School


# serializers for School Partnerships
# region

class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = ('school_id', 'school_name')


class ProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = ('program_id', 'program_name')


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ('department_id', 'department_name')


class CareerEmplacementAdminSerializer(serializers.ModelSerializer):
    school = SchoolSerializer()

    class Meta:
        model = CareerEmplacementAdmin
        fields = ('user', 'school')


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ('company_name', 'company_address', 'business_nature', 'company_website_url', 'linkedin_url')


class CompanyListSerializer(serializers.ModelSerializer):
    company_uuid = serializers.UUIDField(source='user')

    class Meta:
        model = Company
        fields = [
            'company_uuid',
            'company_name',
            'company_address',
            'company_information',
            'business_nature',
            'company_website_url',
            'x_url',
            'facebook_url',
            'linkedin_url',
            'instagram_url',
            'other_url',
        ]


class CreatePartnershipSerializer(serializers.Serializer):
    company_uuids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True
    )

    def validate_company_uuids(self, value):
        companies = Company.objects.filter(user__user_id__in=value, user__status='Active')
        if companies.count() != len(value):
            valid_ids = set(comp.user.user_id for comp in companies)
            invalid_ids = set(value) - valid_ids
            raise serializers.ValidationError(f"One or more UUIDs are invalid or inactive: {list(invalid_ids)}")
        return value

    def create(self, validated_data):
        school = self.context['school']
        company_uuids = validated_data['company_uuids']

        companies = Company.objects.filter(user__user_id__in=company_uuids)

        existing_uuids = set(
            SchoolPartnershipList.objects.filter(
                school=school,
                company__in=companies
            ).values_list('company__user__user_id', flat=True)
        )

        new_partnerships = [
            SchoolPartnershipList(school=school, company=company)
            for company in companies
            if company.user.user_id not in existing_uuids
        ]

        if not new_partnerships:
            raise serializers.ValidationError({
                "company_uuids": [f"Already partnered: {uuid}" for uuid in existing_uuids]
            })

        created_partnerships = SchoolPartnershipList.objects.bulk_create(new_partnerships)

        return created_partnerships


class SchoolPartnershipSerializer(serializers.ModelSerializer):
    company_uuid = serializers.UUIDField(source='company.user.user_id', read_only=True)
    company_name = serializers.CharField(source='company.company_name', read_only=True)
    company_address = serializers.CharField(source='company.company_address', read_only=True)
    company_information = serializers.CharField(source='company.company_information', read_only=True)
    business_nature = serializers.CharField(source='company.business_nature', read_only=True)
    company_website_url = serializers.CharField(source='company.company_website_url', read_only=True)
    x_url = serializers.CharField(source='company.x_url', read_only=True)
    facebook_url = serializers.CharField(source='company.facebook_url', read_only=True)
    linkedin_url = serializers.CharField(source='company.linkedin_url', read_only=True)
    instagram_url = serializers.CharField(source='company.instagram_url', read_only=True)
    other_url = serializers.CharField(source='company.other_url', read_only=True)

    class Meta:
        model = SchoolPartnershipList
        fields = [
            'company_uuid',
            'company_name',
            'company_address',
            'company_information',
            'business_nature',
            'company_website_url',
            'x_url',
            'facebook_url',
            'linkedin_url',
            'instagram_url',
            'other_url',
        ]


