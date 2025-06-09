from django.db import transaction, IntegrityError
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework import generics, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ojt_management.views import ojt_management_tag
from user_account.models import CareerEmplacementAdmin, OJTCoordinator, Applicant, Company, AuditLog, User
from user_account.serializers import GetOJTCoordinatorSerializer, OJTCoordinatorRegisterSerializer, \
    GetApplicantSerializer, EditOJTCoordinatorSerializer
from .models import SchoolPartnershipList
from user_account.permissions import IsCEA
from .serializers import CompanyListSerializer, CreatePartnershipSerializer, SchoolPartnershipSerializer, \
    CareerEmplacementAdminSerializer, CeaAuditLogSerializer

cea_management_tag = extend_schema(tags=["cea_management"])


def log_cea_action(user, action, obj=None, details="", action_type=None):
    if obj:
        model_name = obj.__class__.__name__
        object_id = str(getattr(obj, 'pk', ''))
        object_repr = str(obj)
    else:
        model_name = ""
        object_id = ""
        object_repr = ""

    if action_type not in {'add', 'change', 'delete'}:
        action_type = None

    AuditLog.objects.create(
        user=user,
        user_role='cea',
        action=action,
        model=model_name,
        object_id=object_id,
        object_repr=object_repr,
        details=details,
        action_type=action_type
    )


class CEAMixin:
    # get the cea instance of user & return error if not found
    def get_cea_or_403(self, user):
        try:
            return CareerEmplacementAdmin.objects.get(user=user)
        except CareerEmplacementAdmin.DoesNotExist:
            raise PermissionDenied("User is not a Career Emplacement Admin. Access denied.")


# region OJT Coordinators Management


@cea_management_tag
class OJTCoordinatorListView(CEAMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsCEA]
    serializer_class = GetOJTCoordinatorSerializer

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]

    search_fields = [
        'user__status'
        , 'first_name'
        , 'last_name'
        , 'user__email'
        , 'program__program_name'
        , 'department__department_name'
    ]

    ordering_fields = [
        'user__status'
        , 'first_name'
        , 'last_name'
        , 'user__email'
        , 'program__program_name'
        , 'department__department_name'
    ]

    ordering = ['user__status', 'program__program_name']

    def get_queryset(self):
        cea = self.get_cea_or_403(self.request.user)
        queryset = OJTCoordinator.objects.filter(department__school=cea.school,
                                                 user__status__in=['Active', 'Inactive', 'Suspended'])

        user = self.request.query_params.get('user')
        if user:
            queryset = queryset.filter(user=user)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        if not queryset.exists():
            return Response(
                {'message': 'No OJT Coordinators in the list.'}
            )

        return super().list(request, *args, **kwargs)


@cea_management_tag
class CreateOJTCoordinatorView(CEAMixin, generics.CreateAPIView):
    permission_classes = [IsAuthenticated, IsCEA]
    serializer_class = OJTCoordinatorRegisterSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        cea = self.get_cea_or_403(self.request.user)
        context['school'] = cea.school
        return context

    @transaction.atomic
    def perform_create(self, serializer):
        cea = self.get_cea_or_403(self.request.user)

        program = serializer.validated_data.get('program', None)
        if program and program.department.school != cea.school:
            raise PermissionDenied(
                {'program': ["You can only assign coordinators to programs belonging to your school."]})

        department = serializer.validated_data.get('department', None)
        if not department or department.school != cea.school:
            raise ValidationError({'department': ["The chosen department must belong to your school."]})

        coordinator = serializer.save()

        log_cea_action(
            user=self.request.user,
            action="Created new OJT Coordinator",
            action_type='add',
            obj=coordinator,
            details=f"Assigned to department: {department.department_name},"
                    f" program: {program.program_name if program else 'None'}"
        )


@cea_management_tag
class UpdateOJTCoordinatorView(CEAMixin, generics.UpdateAPIView):
    permission_classes = [IsAuthenticated, IsCEA]
    queryset = OJTCoordinator.objects.all()
    serializer_class = EditOJTCoordinatorSerializer

    def get_object(self):
        user = self.request.query_params.get('user')
        if not user:
            raise ValidationError({"error": "Query parameter 'user' is required."})

        try:
            return self.get_queryset().get(user__user_id=user)
        except OJTCoordinator.DoesNotExist:
            raise ValidationError({"error": f"No OJT Coordinator found for user: {user}"})

    def update(self, request, *args, **kwargs):
        coordinator = self.get_object()
        serializer = self.get_serializer(coordinator, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        serializer.save()

        log_cea_action(
            user=self.request.user,
            action="Updated an OJT Coordinator",
            action_type='change',
            obj=coordinator,
            details=f"Updated OJT Coordinator: {coordinator}"
        )

        return Response(serializer.data)


@cea_management_tag
class RemoveOJTCoordinatorView(CEAMixin, generics.DestroyAPIView):
    permission_classes = [IsAuthenticated, IsCEA]

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

    def delete(self, request, *args, **kwargs):
        coordinator = self.get_object()
        user = coordinator.user

        log_cea_action(
            user=self.request.user,
            action="Deleted OJT Coordinator",
            action_type='delete',
            obj=coordinator,
            details=f"Deleted OJT Coordinator: {coordinator.user.email}"
        )

        user.delete()

        return Response(
            {'message': 'The OJT Coordinator has been deleted.'},
            status=status.HTTP_204_NO_CONTENT
        )


# endregion


# region Student list

@cea_management_tag
class ApplicantListView(CEAMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsCEA]
    serializer_class = GetApplicantSerializer

    filter_backends = [filters.SearchFilter]

    search_fields = [
        'first_name'
        , 'last_name'
        , 'user__email'
        , 'in_practicum'
    ]

    def get_queryset(self):
        cea = self.get_cea_or_403(self.request.user)
        return Applicant.objects.filter(school=cea.school, user__status__in=['Active'])

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        if not queryset.exists():
            return Response(
                {'message': 'Student List is empty.'}
            )

        return super().list(request, *args, **kwargs)


# endregion

# region Company Partnerships -- PAUL

@cea_management_tag
class SchoolPartnershipListView(CEAMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsCEA]
    serializer_class = SchoolPartnershipSerializer

    filter_backends = [filters.SearchFilter]
    search_fields = ['company__company_name']

    def get_queryset(self):
        cea = self.get_cea_or_403(self.request.user)
        queryset = SchoolPartnershipList.objects.filter(
            school=cea.school
            , company__user__status__in=['Active']
        ).select_related('company', 'company__user')
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        if not queryset.exists():
            return Response(
                {'message': 'There are no company partnerships.'},
                status=status.HTTP_200_OK,
            )

        serializer = SchoolPartnershipSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@cea_management_tag
class CreateSchoolPartnershipView(CEAMixin, generics.CreateAPIView):
    permission_classes = [IsAuthenticated, IsCEA]
    serializer_class = CreatePartnershipSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        cea = self.get_cea_or_403(self.request.user)
        context['school'] = cea.school
        return context

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        partnerships = serializer.save()

        school_name = partnerships[0].school.school_name if partnerships else "Unknown School"
        company_names = ", ".join([p.company.company_name for p in partnerships])
        partnership_str = f"{school_name}: {company_names}"

        log_cea_action(
            user=self.request.user,
            action="Created School Partnership(s)",
            action_type='add',
            obj=company_names,
            details=f"Created Partnerships with {partnership_str}"
        )

        read_serializer = SchoolPartnershipSerializer(partnerships, many=True)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)


@cea_management_tag
class CompanyListView(CEAMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsCEA]

    serializer_class = CompanyListSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['company_name']

    def get_queryset(self):
        cea = self.get_cea_or_403(self.request.user)

        partnered_company_ids = SchoolPartnershipList.objects.filter(
            school=cea.school
        ).values_list('company__user__user_id', flat=True)

        return Company.objects.filter(user__status__in=['Active']
                                      ).exclude(user__user_id__in=partnered_company_ids
                                                ).select_related('user')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        if not queryset.exists():
            return Response(
                {'message': 'No Companies found.'},
                status=status.HTTP_200_OK,
            )

        serializer = CompanyListSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@cea_management_tag
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

        school_name = partnerships_qs[0].school.school_name if partnerships_qs else "Unknown School"
        company_names = ", ".join([p.company.company_name for p in partnerships_qs])
        partnership_str = f"{school_name}: {company_names}"

        log_cea_action(
            user=self.request.user,
            action="Deleted School Partnership(s)",
            action_type='delete',
            obj=company_names,
            details=f"Deleted Partnerships from {partnership_str}"
        )

        deleted_count, _ = partnerships_qs.delete()

        return Response(
            {"detail": f"Successfully deleted {deleted_count} school partnership(s)."},
            status=status.HTTP_200_OK,
        )


# endregion


@cea_management_tag
class CareerEmplacementAdminView(CEAMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CareerEmplacementAdminSerializer

    def get_queryset(self):
        user = self.request.user
        if user.user_role != 'cea':
            raise ValidationError({'error': "User must be a Career Emplacement Admin."})

        return CareerEmplacementAdmin.objects.filter(user=user)


@cea_management_tag
class CeaAuditLogView(CEAMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CeaAuditLogSerializer

    def get_queryset(self):
        user = self.request.user
        if user.user_role != 'cea':
            raise ValidationError({'error': 'User must be a Career Emplacement Admin.'})

        return AuditLog.objects.filter(user=user).order_by('-timestamp')[:10]
