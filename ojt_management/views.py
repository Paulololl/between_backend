from rest_framework.exceptions import  PermissionDenied, ValidationError
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .permissions import IsCoordinator
from user_account.models import OJTCoordinator, Applicant
from user_account.serializers import GetApplicantSerializer
from cea_management.models import SchoolPartnershipList
from cea_management.serializers import SchoolPartnershipSerializer


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
    serializer_class = GetApplicantSerializer

    def get_object(self):
        user = self.request.query_params.get('user')
        if not user:
            raise ValidationError({"error": "Query parameter 'user' is required."})
        try:
            instance = self.get_queryset().get(user__user_id=user)
        except Applicant.DoesNotExist:
            raise ValidationError({"error": f"No student found for user: {user}"})
        return instance

    def update(self, request, *args, **kwargs):
        applicant = self.get_object()
        applicant.in_practicum = 'No'
        applicant.save()

        return Response({'message': "The student's practicum has been marked as ended."})

# Students Requesting Practicum List -- KC
class GetRequestPracticumListView(CoordinatorMixin, generics.ListAPIView):
    serializer_class = GetApplicantSerializer

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        queryset = Applicant.objects.filter(program=coordinator.program, user__status__in=['Active'], in_practicum='Pending').select_related('user')

        user = self.request.query_params.get('user')
        if user:
            queryset = queryset.filter(user=user)

        return queryset


# endregion