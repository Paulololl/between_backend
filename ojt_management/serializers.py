from rest_framework import serializers

from client_application.models import Endorsement
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



