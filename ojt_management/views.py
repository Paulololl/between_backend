from rest_framework.exceptions import  PermissionDenied, ValidationError
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .permissions import IsCoordinator
from user_account.models import OJTCoordinator
from cea_management.models import SchoolPartnershipList
from cea_management.serializers import CompanySerializer

class CoordinatorMixin:
    permission_class = [IsAuthenticated, IsCoordinator]

    def get_coordinator_or_403(self, user):
        try:
            return OJTCoordinator.objects.get(user=user)
        except OJTCoordinator.DoesNotExist:
            raise PermissionDenied('User is not an OJT Coordinator. Access denied.')

# School Partnerships
class SchoolPartnershipListView(CoordinatorMixin, generics.ListAPIView):
    serializer_class = CompanySerializer

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        partnerships = SchoolPartnershipList.objects.filter(school=coordinator.program.department.school).select_related('company')
        return [partnership.company for partnership in partnerships]
