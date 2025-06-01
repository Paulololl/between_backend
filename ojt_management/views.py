from rest_framework.exceptions import  PermissionDenied, ValidationError
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .permissions import IsCoordinator
from user_account.models import OJTCoordinator, Applicant
from . import serializers as ojt_serializers


class CoordinatorMixin:
    permission_class = [IsAuthenticated, IsCoordinator]

    def get_coordinator_or_403(self, user):
        try:
            return OJTCoordinator.objects.get(user=user)
        except OJTCoordinator.DoesNotExist:
            raise PermissionDenied('User is not an OJT Coordinator. Access denied.')

# School Partnerships


# Student List
class StudentListView(CoordinatorMixin, generics.ListAPIView):
    serializer_class = ojt_serializers.GetStudentList

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        return Applicant.objects.filter(school=coordinator.program.department.school)
