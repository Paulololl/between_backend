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

