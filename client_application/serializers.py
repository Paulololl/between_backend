from rest_framework import serializers

from client_application.models import Application


class ApplicationListSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='internship_posting.company.company_name')
    internship_position = serializers.CharField(source='internship_posting.internship_position')
    company_address = serializers.CharField(source='internship_posting.company.company_address')
    profile_picture = serializers.SerializerMethodField()
    applicant_name = serializers.SerializerMethodField()
    applicant_address = serializers.CharField(source='applicant.address')

    class Meta:
        model = Application
        fields = ['company_name', 'internship_position', 'company_address', 'profile_picture',
                  'applicant_name', 'internship_position', 'applicant_address',
                  'application_id', 'status']

    def get_applicant_name(self, obj):
        first_name = obj.applicant.first_name or ''
        last_name = obj.applicant.last_name or ''
        middle_initial = obj.applicant.middle_initial or ''

        return f"{last_name}, {first_name} {middle_initial}".strip()

    def get_profile_picture(self, obj):
        image = obj.internship_posting.company.profile_picture
        return self._build_url(image)

    def _build_url(self, image):
        if image and hasattr(image, 'url'):
            return self.context['request'].build_absolute_uri(image.url)
        return None

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        if user and hasattr(user, 'user_role'):
            if user.user_role == 'applicant':
                allowed_fields = ['company_name', 'internship_position', 'company_address', 'profile_picture',
                                  'application_id', 'status']

            elif user.user_role == 'company':
                allowed_fields = ['applicant_name', 'internship_position', 'applicant_address',
                                  'application_id', 'status']

            else:
                allowed_fields = []

            return {field: representation[field] for field in allowed_fields if field in representation}

        return representation

