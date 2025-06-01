from rest_framework.exceptions import  PermissionDenied, ValidationError
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from cea_management import serializers
from client_application.models import Endorsement
from user_account.permissions import IsApplicant
from .permissions import IsCoordinator
from user_account.models import OJTCoordinator, Applicant
from user_account.serializers import GetApplicantSerializer
from cea_management.models import SchoolPartnershipList
from cea_management.serializers import SchoolPartnershipSerializer
from . import serializers as ojt_serializers
from .serializers import EndorsementListSerializer, EndorsementDetailSerializer, RequestEndorsementSerializer


class CoordinatorMixin:
    permission_class = [IsAuthenticated, IsCoordinator]

    def get_coordinator_or_403(self, user):
        try:
            return OJTCoordinator.objects.get(user=user)
        except OJTCoordinator.DoesNotExist:
            raise PermissionDenied('User is not an OJT Coordinator. Access denied.')


# School Partnerships
class SchoolPartnershipListView(CoordinatorMixin, generics.ListAPIView):
    serializer_class = SchoolPartnershipSerializer

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        return SchoolPartnershipList.objects.filter(school=coordinator.program.department.school).select_related('company', 'company__user')


# Student List
class ApplicantListView(CoordinatorMixin, generics.ListAPIView):
    serializer_class = GetApplicantSerializer

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        return Applicant.objects.filter(program__department__school=coordinator.program.department.school, user__status__in=['Active'])


class EndorsementListView(CoordinatorMixin, generics.ListAPIView):
    serializer_class = EndorsementListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        return Endorsement.objects.filter(
            status='Pending',
            program_id=coordinator.program
        )


class RespondedEndorsementListView(CoordinatorMixin, generics.ListAPIView):
    serializer_class = EndorsementListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        return Endorsement.objects.filter(
            program_id=coordinator.program
        ).exclude(status='Pending')


class EndorsementDetailView(CoordinatorMixin, generics.ListAPIView):
    serializer_class = EndorsementDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)

        return Endorsement.objects.filter(
            program_id=coordinator.program_id,
        )


class RequestEndorsementView(generics.CreateAPIView):
    serializer_class = RequestEndorsementSerializer
    permission_classes = [IsAuthenticated, IsApplicant]

    def create(self, request, *args, **kwargs):
        application_id = request.query_params.get('application_id')

        if not application_id:
            return Response({'detail': 'application_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data={})
        serializer.context['request'] = request
        serializer.context['application_id'] = application_id
        serializer.is_valid(raise_exception=True)
        endorsement = serializer.save()

        return Response(self.get_serializer(endorsement).data, status=status.HTTP_201_CREATED)



