from rest_framework import serializers

from user_account.models import User, Company, OJTCoordinator
from .models import SchoolPartnershipList

# serializers for School Partnerships
#region
class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ('company_name', 'company_address', 'business_nature', 'company_website_url', 'linkedin_url')

class SchoolPartnershipSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    company_id = serializers.CharField(write_only=True)

    class Meta:
        model = SchoolPartnershipList
        fields = ('company', 'company_id')

    def validate_company_id(self, value):
        try:
            company = Company.objects.get(company_id=value)
            if company.user.status != 'Active':
                raise serializers.ValidationError('Cannot partner with inactive company')
            return value
        except Company.DoesNotExist:
            raise serializers.ValidationError('Company does not exist')

    def create(self, validated_data):
        school = self.context['school']

        company_id = validated_data.get('company_id')
        if not company_id:
            raise serializers.ValidationError({'company_id': 'This field is required.'})

        company = Company.objects.get(company_id=company_id)

        if SchoolPartnershipList.objects.filter(school=school, company=company).exists():
            raise serializers.ValidationError('School is already partnered with this company')

        partnership = SchoolPartnershipList.objects.create(school=school, company=company)
        return partnership
#endregion
