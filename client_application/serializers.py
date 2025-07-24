import textwrap
from email.utils import formataddr

from django.core.mail import EmailMessage
from rest_framework import serializers

from client_application.models import Application, Notification, Endorsement


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
                  'application_id', 'status', 'application_date', 'applicant_status', 'company_status']

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
                                  'application_id', 'status', 'applicant_status', 'application_date']

            elif user.user_role == 'company':
                allowed_fields = ['applicant_name', 'internship_position', 'applicant_address',
                                  'application_id', 'status', 'company_status', 'application_date']

            else:
                allowed_fields = []

            return {field: representation[field] for field in allowed_fields if field in representation}

        return representation


class ApplicationDetailSerializer(serializers.ModelSerializer):
    company_email = serializers.CharField(source='internship_posting.company.user.email')
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
    applicant_program = serializers.SerializerMethodField(required=False)
    applicant_academic_program = serializers.SerializerMethodField(required=False)
    applicant_resume = serializers.SerializerMethodField()
    applicant_in_practicum = serializers.SerializerMethodField()
    application_status = serializers.CharField(source='status')
    endorsement_status = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = ['company_email', 'company_name', 'internship_position', 'company_address', 'application_modality',
                  'internship_date_start', 'application_deadline', 'date_created', 'other_requirements',
                  'key_tasks', 'min_qualifications', 'benefits', 'company_information', 'company_status',
                  'company_website_url', 'linkedin_url', 'facebook_url', 'instagram_url', 'x_url', 'other_url',
                  'profile_picture',
                  'applicant_name', 'applicant_email', 'applicant_address', 'applicant_modality', 'applicant_program',
                  'applicant_academic_program', 'applicant_resume', 'applicant_status', 'applicant_in_practicum',
                  'application_id', 'application_status', 'endorsement_status']

    def get_endorsement_status(self, obj):
        endorsement = Endorsement.objects.filter(
            application=obj
        ).exclude(
            status='Deleted'
        ).first()
        return endorsement.status if endorsement else None

    def get_applicant_in_practicum(self, obj):
        if obj.applicant and obj.applicant.in_practicum:
            return obj.applicant.in_practicum
        return None

    def get_applicant_academic_program(self, obj):
        if obj.applicant and obj.applicant.academic_program:
            return obj.applicant.academic_program
        return None

    def get_applicant_resume(self, obj):
        if obj.applicant and obj.applicant.resume:
            return self._build_url(obj.applicant.resume)
        return None

    def get_applicant_program(self, obj):
        if obj.applicant and obj.applicant.program and obj.applicant.program.program_name:
            return obj.applicant.program.program_name
        return None

    def get_applicant_modality(self, obj):
        if obj.applicant and obj.applicant.preferred_modality:
            return obj.applicant.preferred_modality
        return None

    def get_applicant_address(self, obj):
        if obj.applicant and obj.applicant.address:
            return obj.applicant.address
        return None

    def get_applicant_email(self, obj):
        if obj.applicant and obj.applicant.user and obj.applicant.user.email:
            return obj.applicant.user.email
        return None

    def get_applicant_name(self, obj):
        if obj.applicant:
            first_name = obj.applicant.first_name or ''
            last_name = obj.applicant.last_name or ''
            middle_initial = obj.applicant.middle_initial or ''
            full_name = f"{last_name}, {first_name} {middle_initial}".strip()
            return full_name if full_name.strip(', ') else None
        return None

    def get_key_tasks(self, obj):
        if obj.internship_posting:
            return [
                key_task.key_task
                for key_task in obj.internship_posting.key_tasks.all()
            ]
        return None

    def get_min_qualifications(self, obj):
        if obj.internship_posting:
            return [
                min_qualification.min_qualification
                for min_qualification in obj.internship_posting.min_qualifications.all()
            ]
        return None

    def get_benefits(self, obj):
        if obj.internship_posting:
            return [
                benefit.benefit
                for benefit in obj.internship_posting.benefits.all()
            ]
        return None

    def get_profile_picture(self, obj):
        if obj.internship_posting and obj.internship_posting.company and obj.internship_posting.company.profile_picture:
            return self._build_url(obj.internship_posting.company.profile_picture)
        return None

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
                allowed_fields = ['application_id', 'company_email', 'company_name', 'internship_position',
                                  'company_address', 'application_modality',
                                  'internship_date_start', 'application_deadline', 'date_created', 'other_requirements',
                                  'key_tasks', 'min_qualifications', 'benefits', 'company_information',
                                  'company_website_url', 'linkedin_url', 'facebook_url', 'instagram_url', 'x_url',
                                  'other_url', 'profile_picture', 'application_status', 'applicant_status',
                                  'applicant_in_practicum', 'endorsement_status']

            elif user.user_role == 'company':
                allowed_fields = ['application_id', 'applicant_name', 'applicant_email', 'internship_position',
                                  'applicant_address', 'applicant_modality', 'applicant_program',
                                  'applicant_academic_program', 'applicant_resume', 'application_id', 'company_status',
                                  'application_status']

            else:
                allowed_fields = []

            return {field: representation[field] for field in allowed_fields if field in representation}

        return representation


class NotificationSerializer(serializers.ModelSerializer):
    internship_position = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['notification_id', 'application', 'created_at', 'notification_text', 'notification_type',
                  'internship_position']

    def get_internship_position(self, obj):
        position = obj.application.internship_posting.internship_position
        return position

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        if user and hasattr(user, 'user_role'):
            if user.user_role == 'applicant':
                allowed_fields = ['notification_id', 'application', 'internship_position', 'created_at',
                                  'notification_text']

            elif user.user_role == 'company':
                allowed_fields = ['notification_id', 'application', 'internship_position', 'created_at',
                                  'notification_text']

            else:
                allowed_fields = []

            return {field: representation[field] for field in allowed_fields if field in representation}

        return representation


class ClearNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = []


class UpdateApplicationSerializer(serializers.ModelSerializer):
    rejection_message = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = Application
        fields = ['application_id', 'status', 'rejection_message']

    def validate_rejection_message(self, value):
        for item in value:
            if len(item) > 500:
                raise serializers.ValidationError({"error": "Rejection message must not exceed 500 characters."})
        return value


class RequestDocumentSerializer(serializers.Serializer):
    application_id = serializers.UUIDField()
    document_list = serializers.CharField(
        max_length=500,
        error_messages={'error': 'The message must not exceed 500 characters.'}
    )
    message = serializers.CharField(
        max_length=500,
        allow_blank=True,
        allow_null=True,
        error_messages={'error': 'The message must not exceed 500 characters.'}
    )

    def validate_application_id(self, value):
        try:
            application = Application.objects.get(application_id=value)
        except Application.DoesNotExist:
            raise serializers.ValidationError({'error': 'Application not found.'})

        self.application = application
        return value

    def send_request_email(self):
        applicant_email = self.application.applicant.user.email
        company_name = self.application.internship_posting.company.company_name

        documents = self.validated_data.get("document_list")
        doc_lines = "\n".join(f"<li>{doc.strip()}</li>" for doc in documents.split(",") if doc.strip())

        message_html = f"""
          <div>
              <p>Dear Applicant,</p>

              <p><strong>{company_name} is requesting the following additional document(s):</strong></p>

              <p>{doc_lines}</p>

              <p><strong>Additional message:</strong><br>{self.validated_data['message']}</p>

              <p>Best regards,<br><strong>{company_name}</strong></p>
          </div>
          """

        email = EmailMessage(
            subject="Request Additional Document/s",
            body=message_html,
            from_email=formataddr((company_name, 'between.internships@gmail.com')),
            to=[applicant_email],
            reply_to=['no-reply@betweeninternships.com']
        )
        email.content_subtype = 'html'
        email.send(fail_silently=False)


class ApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ['application_id', 'status']


class ListApplicationSerializer(serializers.ModelSerializer):
    application_status = serializers.CharField(source='status')
    company_name = serializers.CharField(source='internship_posting.company.company_name')
    internship_position = serializers.CharField(source='internship_posting.internship_position')
    key_tasks = serializers.SerializerMethodField()
    min_qualifications = serializers.SerializerMethodField()
    benefits = serializers.SerializerMethodField()
    required_hard_skills = serializers.SerializerMethodField()
    required_soft_skills = serializers.SerializerMethodField()
    internship_address = serializers.CharField(source='internship_posting.address')
    ojt_hours = serializers.CharField(source='internship_posting.ojt_hours')
    pic_id = serializers.CharField(source='internship_posting.person_in_charge.person_in_charge_id')
    pic_name = serializers.CharField(source='internship_posting.person_in_charge.name')
    pic_position = serializers.CharField(source='internship_posting.person_in_charge.position')
    pic_email = serializers.CharField(source='internship_posting.person_in_charge.email')
    pic_mobile_number = serializers.CharField(source='internship_posting.person_in_charge.mobile_number')
    pic_landline_number = serializers.CharField(source='internship_posting.person_in_charge.landline_number')

    def get_required_hard_skills(self, obj):
        if obj.internship_posting:
            return [
                skill.name
                for skill in obj.internship_posting.required_hard_skills.all()
            ]
        return None

    def get_required_soft_skills(self, obj):
        if obj.internship_posting:
            return [
                skill.name
                for skill in obj.internship_posting.required_soft_skills.all()
            ]
        return None

    def get_min_qualifications(self, obj):
        if obj.internship_posting:
            return [
                min_qualification.min_qualification
                for min_qualification in obj.internship_posting.min_qualifications.all()
            ]
        return None

    def get_benefits(self, obj):
        if obj.internship_posting:
            return [
                benefit.benefit
                for benefit in obj.internship_posting.benefits.all()
            ]
        return None

    def get_key_tasks(self, obj):
        if obj.internship_posting:
            return [
                key_task.key_task
                for key_task in obj.internship_posting.key_tasks.all()
            ]
        return None


class RemoveFromBookmarksSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ['application_id', 'applicant_status', 'company_status']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        if user and hasattr(user, 'user_role'):
            if user.user_role == 'applicant':
                allowed_fields = ['application_id', 'applicant_status']

            elif user.user_role == 'company':
                allowed_fields = ['application_id', 'company_status']

            else:
                allowed_fields = []

            return {field: representation[field] for field in allowed_fields if field in representation}

        return representation


class SendDocumentSerializer(serializers.Serializer):
    application_id = serializers.UUIDField()
    message = serializers.CharField(
        max_length=500,
        allow_blank=True,
        allow_null=True,
        required=False,
        error_messages={'error': 'The message must not exceed 500 characters.'}
    )

    def validate_application_id(self, value):
        try:
            application = Application.objects.get(application_id=value)
        except Application.DoesNotExist:
            raise serializers.ValidationError({'error': 'Application not found.'})
        self.application = application
        return value

    def send_document_email(self, files):
        company_email = self.application.internship_posting.company.user.email
        applicant = self.application.applicant

        subject = (f"Applicant {applicant.first_name} {applicant.middle_initial} {applicant.last_name}"
                   f" submitted additional documents")
        message = self.validated_data.get("message", "")

        message_html = f"""
            <div>
                <p>Dear {self.application.internship_posting.company.company_name},</p>
                <p><strong>{applicant.first_name} {applicant.middle_initial} {applicant.last_name}
                 has submitted additional document(s).</strong></p>
                <p><strong>Additional Message:</strong><br>{message}</p>
                <p>Best regards,<br>{applicant.first_name} {applicant.middle_initial} {applicant.last_name}
                </p>
            </div>
        """

        email = EmailMessage(
            subject=subject,
            body=message_html,
            from_email=formataddr((f'{applicant.first_name} {applicant.middle_initial} {applicant.last_name}',
                                   'between.internships@gmail.com')),
            to=[company_email],
            reply_to=['no-reply@betweeninternships.com']
        )
        email.content_subtype = 'html'

        for f in files:
            email.attach(f.name, f.read(), f.content_type)
            f.seek(0)

        email.send(fail_silently=False)






