from rest_framework.exceptions import  PermissionDenied, ValidationError
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from user_account.permissions import IsCoordinator, IsApplicant
from user_account.models import OJTCoordinator, Applicant
from user_account.serializers import GetApplicantSerializer
from cea_management.models import SchoolPartnershipList
from cea_management.serializers import SchoolPartnershipSerializer
from .serializers import UpdatePracticumStatusSerializer, UploadEnrollmentRecordSerializer


class CoordinatorMixin:
    permission_class = [IsAuthenticated, IsCoordinator]

    def get_coordinator_or_403(self, user):
        try:
            return OJTCoordinator.objects.get(user=user)
        except OJTCoordinator.DoesNotExist:
            raise PermissionDenied('User is not an OJT Coordinator. Access denied.')


# region School Partnerships -- KC
class SchoolPartnershipListView(CoordinatorMixin, generics.ListAPIView):
    serializer_class = SchoolPartnershipSerializer

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        return SchoolPartnershipList.objects.filter(school=coordinator.program.department.school).select_related('company', 'company__user')

# endregion

# region Student List -- KC
class ApplicantListView(CoordinatorMixin, generics.ListAPIView):
    serializer_class = GetApplicantSerializer

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        return Applicant.objects.filter(program=coordinator.program, user__status__in=['Active'])

# endregion

# region Practicum Management

# Students In Practicum List -- KC
class GetPracticumStudentListView(CoordinatorMixin, generics.ListAPIView):
    serializer_class = GetApplicantSerializer

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        queryset = Applicant.objects.filter(program=coordinator.program, user__status__in=['Active'], in_practicum='Yes').select_related('user')

        user = self.request.query_params.get('user')
        if user:
            queryset = queryset.filter(user=user)

        return queryset


#  End Student's Practicum -- KC
class EndPracticumView(CoordinatorMixin, generics.UpdateAPIView):
    queryset = Applicant.objects.all()
    serializer_class = UpdatePracticumStatusSerializer

    def get_object(self):
        user = self.request.query_params.get('user')
        if not user:
            raise ValidationError({"error": "Query parameter 'user' is required."})
        try:
            instance = self.get_queryset().get(user__user_id=user)
        except Applicant.DoesNotExist:
            raise ValidationError({"error": f"No student found for user: {user}"})
        return instance

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['email_message'] = (
            'Congratulations! You have successfully completed your practicum.\n\n'
            'Best regards, \nYour OJT Coordinator'
        )
        context['coordinator'] = self.get_coordinator_or_403(self.request.user)
        return context

    def update(self, request, *args, **kwargs):
        applicant = self.get_object()

        if applicant.in_practicum != 'Yes':
            return Response({'error': 'Action not allowed. Student is not currently in practicum.'})

        if not applicant.enrollment_record:
            return Response({'error': 'Action not allowed. Student has not submitted enrollment record.'})

        request.data['in_practicum'] = 'No'
        return super().update(request, *args, **kwargs)


# Students Requesting Practicum List -- KC
class GetRequestPracticumListView(CoordinatorMixin, generics.ListAPIView):
    serializer_class = GetApplicantSerializer

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        queryset = Applicant.objects.filter(program=coordinator.program, user__status__in=['Active'], in_practicum='Pending', enrollment_record__isnull=False).select_related('user')

        user = self.request.query_params.get('user')
        if user:
            queryset = queryset.filter(user=user)

        return queryset


# Approve Practicum Request -- KC
class ApprovePracticumRequestView(CoordinatorMixin, generics.UpdateAPIView):
    queryset = Applicant.objects.all()
    serializer_class = UpdatePracticumStatusSerializer

    def get_object(self):
        user = self.request.query_params.get('user')
        if not user:
            raise ValidationError({"error": "Query parameter 'user' is required."})
        try:
            instance = self.get_queryset().get(user__user_id=user)
        except Applicant.DoesNotExist:
            raise ValidationError({"error": f"No student found for user: {user}"})
        return instance

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['email_message'] = (
            'Your request for practicum has been approved. Best of luck!\n\n'
            'Best regards, \nYour OJT Coordinator'
        )
        context['coordinator'] = self.get_coordinator_or_403(self.request.user)
        return context

    def update(self, request, *args, **kwargs):
        applicant = self.get_object()

        if applicant.in_practicum != 'Pending':
            return Response({'error': 'Action not allowed. Student has not requested to be in practicum.'})

        if not applicant.enrollment_record:
            return Response({'error': 'Action not allowed. Student has not submitted enrollment record.'})

        request.data['in_practicum'] = 'Yes'
        return super().update(request, *args, **kwargs)


# Reject Practicum Request -- KC
class RejectPracticumRequestView(CoordinatorMixin, generics.UpdateAPIView):
    queryset = Applicant.objects.all()
    serializer_class = UpdatePracticumStatusSerializer

    def get_object(self):
        user = self.request.query_params.get('user')
        if not user:
            raise ValidationError({"error": "Query parameter 'user' is required."})
        try:
            instance = self.get_queryset().get(user__user_id=user)
        except Applicant.DoesNotExist:
            raise ValidationError({"error": f"No student found for user: {user}"})
        return instance

    def get_serializer_context(self):
        context = super().get_serializer_context()

        rejection_reason = self.request.data.get('reason', '').strip()
        if not rejection_reason:
            raise ValidationError({"error": "A reason for rejecting the request is required."})

        context['email_message'] = (
            'Your request for practicum has been rejected for the following reason:\n'
            f'{rejection_reason} \n\n'
            'Best regards, \nYour OJT Coordinator'
        )
        context['coordinator'] = self.get_coordinator_or_403(self.request.user)
        return context

    def update(self, request, *args, **kwargs):
        applicant = self.get_object()

        if applicant.in_practicum != 'Pending':
            return Response({'error': 'Action not allowed. Student has not requested to be in practicum.'})

        if not applicant.enrollment_record:
            return Response({'error': 'Action not allowed. Student has not submitted enrollment record.'})

        request.data['in_practicum'] = 'No'
        return super().update(request, *args, **kwargs)

# Applicant: Request for Practicum -- KC
class RequestPracticumView(generics.UpdateAPIView):
    permission_class = [IsAuthenticated, IsApplicant]
    serializer_class = UpdatePracticumStatusSerializer

    def update(self, request, *args, **kwargs):
        applicant = request.user.applicant
        if not applicant:
            return Response({'error': 'Applicant account not found.'})

        applicant.in_practicum = 'Pending'

        document_serializer = UploadEnrollmentRecordSerializer(data=request.data)
        if document_serializer.is_valid():
            document_serializer.save()
        else:
            return Response(document_serializer.errors)

        applicant.save()

        return Response({'message': 'Request for practicum submitted successfully.'})



# endregion