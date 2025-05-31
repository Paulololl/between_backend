from django.db import transaction, IntegrityError
from rest_framework.exceptions import  PermissionDenied, ValidationError
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from user_account.models import CareerEmplacementAdmin, OJTCoordinator, Applicant
from user_account.serializers import GetOJTCoordinatorSerializer, OJTCoordinatorRegisterSerializer, GetApplicantSerializer
from .models import SchoolPartnershipList, Program, Department
from .permissions import IsCEA
from . import serializers as cea_serializers



class CEAMixin:
    permission_classes = [IsAuthenticated, IsCEA]

    # get the cea instance of user & return error if not found
    def get_cea_or_403(self, user):
        try:
            return CareerEmplacementAdmin.objects.get(user=user)
        except CareerEmplacementAdmin.DoesNotExist:
            raise PermissionDenied("User is not a Career Emplacement Admin. Access denied.")


# views for School Partnerships
#region
class SchoolPartnershipListView(CEAMixin, generics.ListAPIView):
    serializer_class = cea_serializers.CompanySerializer

    def get_queryset(self):
        cea = self.get_cea_or_403(self.request.user)
        partnerships = SchoolPartnershipList.objects.filter(school=cea.school).select_related('company')
        return [partnership.company for partnership in partnerships]


class CreateSchoolPartnershipView(CEAMixin, generics.CreateAPIView):
    serializer_class = cea_serializers.SchoolPartnershipSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        cea = self.get_cea_or_403(self.request.user)
        context['school'] = cea.school
        return context

    def perform_create(self, serializer):
        serializer.save()

class DeleteSchoolPartnershipView(CEAMixin, generics.DestroyAPIView):
    serializer_class = cea_serializers.SchoolPartnershipSerializer
    queryset = SchoolPartnershipList.objects.all()
    lookup_field = 'company_id'

    def get_object(self):
        obj = super().get_object()
        cea = self.get_cea_or_403(self.request.user)
        if obj.school != cea.school:
            raise PermissionDenied("You do not have permission to delete this school partnership.")
        return obj
#endregion

# views for OJT Coordinators
#region
class OJTCoordinatorListView(CEAMixin, generics.ListAPIView):
    serializer_class = GetOJTCoordinatorSerializer

    def get_queryset(self):
        cea = self.get_cea_or_403(self.request.user)
        return OJTCoordinator.objects.filter(program__department__school=cea.school, user__status__in=['Active', 'Inactive'])


    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        modified_data = []
        for item in serializer.data:

            program_id = item.pop('program', None)
            program_name = None
            if program_id:
                program = Program.objects.get(program_id=program_id)
                program_name = program.program_name if program else None
            item['program_name'] = program_name

            """
                        ojt_coordinator_id = item.get('ojt_coordinator_id')
            if ojt_coordinator_id:
                try:
                    ojt_coordinator = OJTCoordinator.objects.get(ojt_coordinator_id=ojt_coordinator_id)
                    item['user_email'] = ojt_coordinator.user.email
                except OJTCoordinator.DoesNotExist:
                    item['user_email'] = None
            """

            modified_data.append(item)

        return Response(modified_data)


class CreateOJTCoordinatorView(CEAMixin, generics.CreateAPIView):
    serializer_class = OJTCoordinatorRegisterSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        cea = self.get_cea_or_403(self.request.user)
        program = serializer.validated_data['program']

        if program.department.school != cea.school:
            raise PermissionDenied("You can only assign coordinators to programs belonging to your school.")

        try:
            serializer.save()
        except IntegrityError as e:
            if "Duplicate entry" in str(e):
                raise ValidationError({"program": ["An OJT Coordinator is already assigned to this program."]})
            raise e

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        data = response.data

        program = Program.objects.get(program_id=data['program'])
        data['program_name'] = program.program_name
        data.pop('program', None)

        data.pop('id', None)

        return Response(data)


class UpdateOJTCoordinatorView(CEAMixin, generics.UpdateAPIView):
    queryset = OJTCoordinator.objects.all()
    serializer_class = OJTCoordinatorRegisterSerializer
    lookup_field = 'ojt_coordinator_id'

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        cea = self.get_cea_or_403(self.request.user)

        # Check attempted status change
        new_status = request.data.get('status', '').capitalize()
        current_status = instance.user.status

        # Prevent transition from 'Deleted' to any other status unless enforced by an admin
        if current_status == 'Deleted' and new_status != 'Deleted':
            raise PermissionDenied(
                "You cannot reactivate an OJT Coordinator who has been deleted. Please contact an administrator."
            )

        # If attempting to mark as 'Deleted', ensure permission to do so
        if new_status == 'Deleted':
            raise PermissionDenied(
                "You cannot directly mark an OJT Coordinator as 'Deleted'. Contact an administrator.")

        # Proceed with the update
        response = super().update(request, *args, **kwargs)

        # Add extra context to the response if needed
        data = response.data
        program = Program.objects.get(program_id=data['program'])
        data['program_name'] = program.program_name
        data.pop('program', None)

        return Response(data)


class RemoveOJTCoordinatorView(CEAMixin, generics.UpdateAPIView):
    queryset = OJTCoordinator.objects.all()
    serializer_class = GetOJTCoordinatorSerializer
    lookup_field = 'ojt_coordinator_id'

    def update(self, request, *args, **kwargs):
        coordinator = self.get_object()
        cea = self.get_cea_or_403(self.request.user)
        coordinator.user.status = 'Deleted'
        coordinator.user.save()

        return Response({'message': 'The OJT Coordinator has been removed.'})
#endregion

# view for student list
#region
class ApplicantListView(CEAMixin, generics.ListAPIView):
    serializer_class = GetApplicantSerializer

    def get_queryset(self):
        cea = self.get_cea_or_403(self.request.user)
        return Applicant.objects.filter(program__department__school=cea.school, user__status__in=['Active', 'Inactive'])


    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        modified_data = []
        for item in serializer.data:
            user = item.pop('user', None)
            if user and isinstance(user, dict):
                user.pop('user_id', None)

            modified_data.append(item)

        return Response(modified_data)
#endregion