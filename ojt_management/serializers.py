from django.core.mail import send_mail
from rest_framework import serializers

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

class UpdatePracticumStatusSerializer(serializers.ModelSerializer):
    in_practicum = serializers.CharField(max_length=10)

    class Meta:
        model = Applicant
        fields = ['in_practicum']

    def validate_in_practicum(self, value):
        allowed_values = ['Yes', 'No', 'Pending']
        if value not in allowed_values:
            raise serializers.ValidationError(f"Invalid value: {value}. Allowed values are: {allowed_values}")
        return value

    def update(self, instance, validated_data):
        new_status = validated_data.get('in_practicum', instance.in_practicum)
        instance.in_practicum = new_status
        instance.save()

        email_message = self.context.get('email_message')
        coordinator = self.context.get('coordinator')

        if email_message:
            self.send_email_to_applicant(instance, coordinator, email_message)

        return instance

    def send_email_to_applicant(self, applicant, coordinator, email_message):
        subject = 'Practicum Status Update'
        recipient_email = applicant.user.email
        coordinator_email = coordinator.user.email
        sender_email = 'no-reply@betweeninternships.com'

        recipient_list = [recipient_email, coordinator_email]

        send_mail(
            subject,
            email_message,
            sender_email,
            recipient_list,
            fail_silently=False,
        )


