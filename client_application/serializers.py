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


class ApplicationDetailSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='internship_posting.company.company_name')
    internship_position = serializers.CharField(source='internship_posting.internship_position')
    company_address = serializers.CharField(source='internship_posting.company.company_address')
    application_modality = serializers.CharField(source='internship_posting.modality')
    internship_date_start = serializers.DateTimeField(source='internship_posting.internship_date_start')
    application_deadline = serializers.DateTimeField(source='internship_posting.application_deadline')
    date_created = serializers.DateTimeField(source='internship_posting.date_created')
    other_requirements = serializers.CharField(source='internship_posting.other_requirements')
    key_tasks = serializers.SerializerMethodField()
    min_qualifications = serializers.SerializerMethodField()
    benefits = serializers.SerializerMethodField()
    company_information = serializers.CharField(source='internship_posting.company.company_information')
    company_website_url = serializers.CharField(source='internship_posting.company.company_website_url')
    linkedin_url = serializers.CharField(source='internship_posting.company.linkedin_url')
    facebook_url = serializers.CharField(source='internship_posting.company.facebook_url')
    instagram_url = serializers.CharField(source='internship_posting.company.instagram_url')
    x_url = serializers.CharField(source='internship_posting.company.x_url')
    other_url = serializers.CharField(source='internship_posting.company.other_url')
    profile_picture = serializers.SerializerMethodField()
    applicant_name = serializers.SerializerMethodField()
    applicant_email = serializers.SerializerMethodField()
    applicant_address = serializers.SerializerMethodField()
    applicant_modality = serializers.SerializerMethodField()
    applicant_program = serializers.SerializerMethodField()
    applicant_resume = serializers.SerializerMethodField()
    application_status = serializers.CharField(source='status')

    class Meta:
        model = Application
        fields = ['company_name', 'internship_position', 'company_address', 'application_modality',
                  'internship_date_start', 'application_deadline', 'date_created', 'other_requirements',
                  'key_tasks', 'min_qualifications', 'benefits', 'company_information',
                  'company_website_url', 'linkedin_url', 'facebook_url', 'instagram_url', 'x_url', 'other_url',
                  'profile_picture',
                  'applicant_name', 'applicant_email', 'applicant_address', 'applicant_modality', 'applicant_program',
                  'applicant_resume',
                  'application_id', 'application_status']

    def get_applicant_resume(self, obj):
        image = obj.applicant.resume
        return self._build_url(image)

    def get_applicant_program(self, obj):
        applicant_program = obj.applicant.program.program_name
        return applicant_program

    def get_applicant_modality(self, obj):
        applicant_modality = obj.applicant.preferred_modality
        return applicant_modality

    def get_applicant_address(self, obj):
        applicant_address = obj.applicant.address
        return applicant_address

    def get_applicant_email(self, obj):
        applicant_user_email = obj.applicant.user.email
        return applicant_user_email

    def get_applicant_name(self, obj):
        first_name = obj.applicant.first_name or ''
        last_name = obj.applicant.last_name or ''
        middle_initial = obj.applicant.middle_initial or ''

        return f"{last_name}, {first_name} {middle_initial}".strip()

    def get_key_tasks(self, obj):
        return [
            key_task.key_task
            for key_task in obj.internship_posting.key_tasks.all()
        ]

    def get_min_qualifications(self, obj):
        return [
            min_qualification.min_qualification
            for min_qualification in obj.internship_posting.min_qualifications.all()
        ]

    def get_benefits(self, obj):
        return [
            benefit.benefit
            for benefit in obj.internship_posting.benefits.all()
        ]

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
                allowed_fields = ['application_id', 'company_name', 'internship_position', 'company_address',
                                  'application_modality',
                                  'internship_date_start', 'application_deadline', 'date_created', 'other_requirements',
                                  'key_tasks', 'min_qualifications', 'benefits', 'company_information',
                                  'company_website_url', 'linkedin_url', 'facebook_url', 'instagram_url', 'x_url',
                                  'other_url', 'profile_picture', 'application_status']

            elif user.user_role == 'company':
                allowed_fields = ['application_id', 'applicant_name', 'applicant_email', 'internship_position',
                                  'applicant_address', 'applicant_modality', 'applicant_program',
                                  'applicant_resume', 'application_id', 'application_status']

            else:
                allowed_fields = []

            return {field: representation[field] for field in allowed_fields if field in representation}

        return representation
