from rest_framework import serializers

from client_application.models import Endorsement, Application
from user_account.models import Applicant


class GetStudentList(serializers.ModelSerializer):
    class Meta:
        model = Applicant
        fields = (
            'user'
            , 'first_name'
            , 'last_name'
            , 'middle_initial'
            , 'in_practicum'
            , 'academic_program'
        )


class EndorsementListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Endorsement
        fields = ['endorsement_id',
                  'program_id',
                  'application',
                  'comments',
                  'date_approved',
                  'status']


class EndorsementDetailSerializer(serializers.ModelSerializer):
    student_email = serializers.EmailField(source='application.applicant.user.email')
    student_name = serializers.SerializerMethodField()
    internship_position = serializers.CharField(source='application.internship_posting.internship_position')
    company_name = serializers.CharField(source='application.internship_posting.company.company_name')
    company_address = serializers.CharField(source='application.internship_posting.company.company_address')
    business_nature = serializers.CharField(source='application.internship_posting.company.business_nature')
    company_website_url = serializers.CharField(source='application.internship_posting.company.company_website_url')
    person_in_charge = serializers.CharField(source='application.internship_posting.person_in_charge')
    person_in_charge_position = serializers.CharField(source='application.internship_posting.person_in_charge.position')
    person_in_charge_email = serializers.CharField(source='application.internship_posting.person_in_charge.email')
    person_in_charge_mobile_number = serializers.CharField(source='application.internship_posting.person_in_charge'
                                                                  '.mobile_number')
    person_in_charge_landline_number = serializers.CharField(source='application.internship_posting.person_in_charge'
                                                                    '.landline_number')
    resume = serializers.SerializerMethodField()
    key_tasks = serializers.SerializerMethodField()
    ojt_hours = serializers.CharField(source='application.internship_posting.ojt_hours')

    class Meta:
        model = Endorsement
        fields = ['endorsement_id',
                  'student_email',
                  'student_name',
                  'internship_position',
                  'company_name',
                  'company_address',
                  'business_nature',
                  'company_website_url',
                  'person_in_charge',
                  'person_in_charge_position',
                  'person_in_charge_email',
                  'person_in_charge_mobile_number',
                  'person_in_charge_landline_number',
                  'resume',
                  'key_tasks',
                  'comments',
                  'date_approved',
                  'ojt_hours',
                  'status'
                  ]

    def get_key_tasks(self, obj):
        return [
            {
                "id": key_task.key_task_id,
                "key_task": key_task.key_task
            }
            for key_task in obj.application.internship_posting.key_tasks.all()
        ]

    def get_resume(self, obj):
        if obj.application.applicant and obj.application.applicant.resume:
            return self._build_url(obj.application.applicant.resume)
        return None

    def _build_url(self, image):
        if image and hasattr(image, 'url'):
            return self.context['request'].build_absolute_uri(image.url)
        return None

    def get_student_name(self, obj):
        if obj.application.applicant:
            first_name = obj.application.applicant.first_name or ''
            last_name = obj.application.applicant.last_name or ''
            middle_initial = obj.application.applicant.middle_initial or ''
            full_name = f"{last_name}, {first_name} {middle_initial}".strip()
            return full_name if full_name.strip(', ') else None
        return None


class RequestEndorsementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Endorsement
        fields = ['endorsement_id', 'program_id', 'application', 'status', 'comments', 'date_approved']
        read_only_fields = ['endorsement_id', 'program_id', 'application', 'status', 'date_approved']

    def validate(self, attrs):
        user = self.context['request'].user
        applicant = getattr(user, 'applicant', None)
        application_id = self.context.get('application_id')

        if not applicant:
            raise serializers.ValidationError("Only applicants can request endorsements.")

        if applicant.in_practicum != "Yes":
            raise serializers.ValidationError("Applicant must be in practicum to request an endorsement.")

        if not application_id:
            raise serializers.ValidationError("Application ID is required.")

        try:
            application = Application.objects.get(application_id=application_id, applicant=applicant)
        except Application.DoesNotExist:
            raise serializers.ValidationError("Application not found or does not belong to you.")

        attrs['application'] = application
        attrs['program_id'] = applicant.program

        return attrs

    def create(self, validated_data):
        application = validated_data['application']
        program = validated_data['program_id']

        existing_endorsement = Endorsement.objects.filter(application=application, program_id=program).first()

        if existing_endorsement:
            if existing_endorsement.status in ['Pending', 'Approved']:
                raise (serializers.ValidationError
                       ({'error': f"An endorsement already exists with status '{existing_endorsement.status}'. " 
                                  f"You cannot request a new one unless it was rejected."}))

        endorsement, created = Endorsement.objects.update_or_create(
            application=application,
            program_id=program,
            defaults={'status': 'Pending'}
        )
        return endorsement


class UpdateEndorsementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Endorsement
        fields = ['endorsement_id', 'status', 'comments']

    def validate(self, attrs):
        status = attrs.get('status')
        comments = attrs.get('comments')

        if status == 'Rejected' and not comments:
            raise serializers.ValidationError({
                'comments': 'Comments are required when rejecting an endorsement.'
            })

        return attrs
