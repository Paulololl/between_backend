from django.db import transaction, IntegrityError
from rest_framework.exceptions import  PermissionDenied, ValidationError
from rest_framework import generics, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from user_account.models import CareerEmplacementAdmin, OJTCoordinator, Applicant, Company
from user_account.serializers import GetOJTCoordinatorSerializer, OJTCoordinatorRegisterSerializer, GetApplicantSerializer, EditOJTCoordinatorSerializer
from .models import SchoolPartnershipList
from user_account.permissions import IsCEA
from .serializers import CompanyListSerializer, CreatePartnershipSerializer, SchoolPartnershipSerializer


class CEAMixin:
    permission_classes = [IsAuthenticated, IsCEA]

    # get the cea instance of user & return error if not found
    def get_cea_or_403(self, user):
        try:
            return CareerEmplacementAdmin.objects.get(user=user)
        except CareerEmplacementAdmin.DoesNotExist:
            raise PermissionDenied("User is not a Career Emplacement Admin. Access denied.")


# OJT Coordinators -- KC
#region
class OJTCoordinatorListView(CEAMixin, generics.ListAPIView):
    serializer_class = GetOJTCoordinatorSerializer

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]

    search_fields = [
        'user__status'
        , 'first_name'
        , 'last_name'
        , 'user__email'
        , 'program__program_name'
    ]

    ordering_fields = [
        'user__status'
        , 'first_name'
        , 'last_name'
        , 'user__email'
        , 'program__program_name'
    ]

    ordering = ['user__status', 'program__program_name']

    def get_queryset(self):
        cea = self.get_cea_or_403(self.request.user)
        queryset = OJTCoordinator.objects.filter(program__department__school=cea.school, user__status__in=['Active', 'Inactive', 'Suspended'])

        user = self.request.query_params.get('user')

        if user:
            queryset = queryset.filter(user=user)

        return queryset


class CreateOJTCoordinatorView(CEAMixin, generics.CreateAPIView):
    serializer_class = OJTCoordinatorRegisterSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        cea = self.get_cea_or_403(self.request.user)
        program = serializer.validated_data['program']

        if program.department.school != cea.school:
            raise PermissionDenied("You can only assign coordinators to programs belonging to your school.")

        existing_coordinators = OJTCoordinator.objects.filter(program=program, user__status__in=['Active', 'Inactive', 'Suspended']).first()
        if existing_coordinators:
            raise ValidationError({"program": ["This program already has an assigned OJT coordinator."]})

        try:
            serializer.save()
        except IntegrityError as e:
            if "Duplicate entry" in str(e):
                raise ValidationError({"program": ["An OJT Coordinator is already assigned to this program."]})
            raise e


class UpdateOJTCoordinatorView(CEAMixin, generics.UpdateAPIView):
    queryset = OJTCoordinator.objects.all()
    serializer_class = EditOJTCoordinatorSerializer

    def get_object(self):
        user = self.request.query_params.get('user')  # Get the user from the query parameters
        if not user:
            raise ValidationError({"error": "Query parameter 'user' is required."})

        # Get the OJT coordinator using the user ID
        try:
            instance = self.get_queryset().get(user__user_id=user)
        except OJTCoordinator.DoesNotExist:
            raise ValidationError({"error": f"No OJT Coordinator found for user: {user}"})

        return instance

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Retrieve the program from the request data, if provided
        program = serializer.validated_data.get('program', None)

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

        if program:
            # Ensure no other Active/Inactive coordinator is assigned to the program
            existing_coordinators = OJTCoordinator.objects.filter(program=program, user__status__in=['Active', 'Inactive', 'Suspended']).exclude(pk=instance.pk).first()

            if existing_coordinators:
                raise ValidationError({"program": ["This program already has an assigned OJT coordinator."]})

        # Proceed with the update
        serializer.save()

        return Response(serializer.data)


class RemoveOJTCoordinatorView(CEAMixin, generics.UpdateAPIView):

    queryset = OJTCoordinator.objects.all()
    serializer_class = GetOJTCoordinatorSerializer

    def get_object(self):
        user = self.request.query_params.get('user')
        if not user:
            raise ValidationError({"error": "Query parameter 'user' is required."})

        try:
            instance = self.get_queryset().get(user__user_id=user)
        except OJTCoordinator.DoesNotExist:
            raise ValidationError({"error": f"No OJT Coordinator found for user: {user}"})

        return instance

    def update(self, request, *args, **kwargs):
        coordinator = self.get_object()
        coordinator.user.status = 'Deleted'
        coordinator.user.save()

        return Response({'message': 'The OJT Coordinator has been removed.'})
#endregion

# Student list --KC
#region
class ApplicantListView(CEAMixin, generics.ListAPIView):
    serializer_class = GetApplicantSerializer

    def get_queryset(self):
        cea = self.get_cea_or_403(self.request.user)
        return Applicant.objects.filter(program__department__school=cea.school, user__status__in=['Active'])


#endregion

# region Company Partnerships -- PAUL
class SchoolPartnershipListView(CEAMixin, generics.ListAPIView):
    serializer_class = SchoolPartnershipSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        cea = self.get_cea_or_403(self.request.user)
        return SchoolPartnershipList.objects.filter(school=cea.school).select_related('company', 'company__user')


class CreateSchoolPartnershipView(CEAMixin, generics.CreateAPIView):
    serializer_class = CreatePartnershipSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        cea = self.get_cea_or_403(self.request.user)
        context['school'] = cea.school
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        partnerships = serializer.save()

        read_serializer = SchoolPartnershipSerializer(partnerships, many=True)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)


class BulkDeleteSchoolPartnershipView(CEAMixin, generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        cea = self.get_cea_or_403(self.request.user)

        company_uuids = request.data.get('company_uuids')

        if not company_uuids or not isinstance(company_uuids, list):
            raise ValidationError({"company_uuids": "A list of company UUIDs is required."})

        companies = Company.objects.filter(user__user_id__in=company_uuids)
        found_uuids = set(str(c.user.user_id) for c in companies)
        missing_uuids = set(company_uuids) - found_uuids

        if missing_uuids:
            raise ValidationError({"error": f"Companies not found: {list(missing_uuids)}"})

        partnerships_qs = SchoolPartnershipList.objects.filter(
            school=cea.school,
            company__in=companies
        )

        if not partnerships_qs.exists():
            return Response(
                {"detail": "No partnerships found to delete."},
                status=status.HTTP_404_NOT_FOUND,
            )

        deleted_count, _ = partnerships_qs.delete()

        return Response(
            {"detail": f"Successfully deleted {deleted_count} school partnership(s)."},
            status=status.HTTP_200_OK,
        )


class CompanyListView(CEAMixin, generics.ListAPIView):
    serializer_class = CompanyListSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['company_name']

    def get_queryset(self):
        try:
            cea = CareerEmplacementAdmin.objects.select_related('school').get(user=self.request.user)
        except CareerEmplacementAdmin.DoesNotExist:
            raise PermissionDenied("Only Career Emplacement Admins can access this list.")

        partnered_company_ids = SchoolPartnershipList.objects.filter(
            school=cea.school
        ).values_list('company__user__user_id', flat=True)

        return Company.objects.exclude(user__user_id__in=partnered_company_ids).select_related('user')

# endregion