import base64
import io
import ssl
import uuid
from datetime import date
from email.utils import formataddr

import requests
from django.core.files.base import ContentFile
from django.core.mail import send_mail, EmailMessage
from django.db import transaction
from django.db.models import OuterRef, Exists
from django.http import HttpResponse
from django.template.loader import render_to_string
from django_extensions.management.commands.export_emails import full_name
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework import generics, status, filters, request
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# from weasyprint import HTML

from between_ims import settings
from between_ims.settings import WEASYPRINT_SERVICE_URL
from cea_management import serializers
from client_application.models import Endorsement, Application
from client_matching.models import InternshipPosting
from client_matching.serializers import InternshipPostingListSerializer
from user_account.permissions import IsCoordinator, IsApplicant
from user_account.models import OJTCoordinator, Applicant, AuditLog
from user_account.serializers import GetApplicantSerializer, OJTCoordinatorDocumentSerializer, AuditLogSerializer, \
    GetOJTCoordinatorSerializer
from cea_management.models import SchoolPartnershipList
from cea_management.serializers import SchoolPartnershipSerializer
from user_account.utils import validate_file_size
from .serializers import EndorsementDetailSerializer, RequestEndorsementSerializer, \
    UpdatePracticumStatusSerializer, UpdateEndorsementSerializer, EnrollmentRecordSerializer, EndorsementListSerializer, \
    GetOJTCoordinatorRespondedEndorsementsSerializer

ojt_management_tag = extend_schema(tags=["ojt_management"])


def log_coordinator_action(user, action, obj=None, details="", action_type=None):
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
        user_role='coordinator',
        action=action,
        model=model_name,
        object_id=object_id,
        object_repr=object_repr,
        details=details,
        action_type=action_type
    )


class CoordinatorMixin:
    def get_coordinator_or_403(self, user):
        try:
            return OJTCoordinator.objects.get(user=user)
        except OJTCoordinator.DoesNotExist:
            raise PermissionDenied('User is not an OJT Coordinator. Access denied.')


@ojt_management_tag
class GetInternshipPostingCoordinatorView(ListAPIView):
    permission_classes = [IsAuthenticated, IsCoordinator]
    serializer_class = InternshipPostingListSerializer

    def get_queryset(self):
        internship_posting_id = self.request.query_params.get("internship_posting_id")

        if not internship_posting_id:
            raise ValidationError({"internship_posting_id": "This query parameter is required."})

        queryset = InternshipPosting.objects.filter(internship_posting_id=internship_posting_id)

        if not queryset.exists():
            raise ValidationError({"error": "Internship posting not found."})

        return queryset


# region School Partnerships -- KC
@ojt_management_tag
class SchoolPartnershipListView(CoordinatorMixin, generics.ListAPIView):
    permission_class = [IsAuthenticated, IsCoordinator]
    serializer_class = SchoolPartnershipSerializer

    filter_backends = [filters.SearchFilter]
    search_fields = ['company__company_name']

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        return SchoolPartnershipList.objects.filter(school=coordinator.department.school).select_related(
            'company', 'company__user')

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            if not queryset:
                return Response({'message': 'No school partnerships found.'})

            return super().list(request, *args, **kwargs)
        except Exception as e:
            raise ValidationError({'error': f'An error occurred while retrieving school partnerships: {str(e)}'})


# endregion

# region Student List -- KC
@ojt_management_tag
class ApplicantListView(CoordinatorMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsCoordinator]
    serializer_class = GetApplicantSerializer

    filter_backends = [filters.SearchFilter]

    search_fields = [
        'first_name'
        , 'last_name'
        , 'user__email'
        , 'in_practicum'
    ]

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        queryset = Applicant.objects.filter(
            program=coordinator.program,
            user__status__in=['Active']
        ).exclude(program__isnull=True)

        user = self.request.query_params.get('user')

        if user:
            queryset = queryset.filter(user=user)

        return queryset

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            if not queryset:
                return Response({'message': 'No students found.'})

            return super().list(request, *args, **kwargs)
        except Exception as e:
            raise ValidationError({'error': f'An error occurred while retrieving students: {str(e)}'})

# endregion

# region Practicum Management


# Students In Practicum List -- KC
@ojt_management_tag
class GetPracticumStudentListView(CoordinatorMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsCoordinator]
    serializer_class = GetApplicantSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['first_name', 'last_name', 'user__email']

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        status_filter = self.request.query_params.get('application_status')
        user_filter = self.request.query_params.get('user')

        base_queryset = Applicant.objects.filter(
            program=coordinator.program,
            user__status='Active',
            in_practicum='Yes',
            enrollment_record__isnull=False,
        ).select_related(
            'user', 'school', 'department', 'program'
        ).prefetch_related(
            'hard_skills', 'soft_skills',
            'applications__internship_posting__required_hard_skills',
            'applications__internship_posting__required_soft_skills',
            'applications__internship_posting__key_tasks',
            'applications__internship_posting__min_qualifications',
            'applications__internship_posting__benefits',
            'applications__internship_posting__company',
            'applications__internship_posting__person_in_charge',
        )

        if status_filter == 'Accepted':
            base_queryset = base_queryset.filter(applications__status='Accepted').distinct()

        elif status_filter == 'Pending':
            # Get applicants who do NOT have any accepted applications
            accepted_applications = Application.objects.filter(
                applicant=OuterRef('pk'), status='Accepted'
            )
            base_queryset = base_queryset.annotate(
                has_accepted=Exists(accepted_applications)
            ).filter(has_accepted=False)

        if user_filter:
            base_queryset = base_queryset.filter(user=user_filter)

        return base_queryset

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            if not queryset.exists():
                return Response({'message': 'No students found.'})
            return super().list(request, *args, **kwargs)
        except Exception as e:
            raise ValidationError({'error': f'An error occurred while retrieving students: {str(e)}'})


class PracticumStudentApplicationStatusView(CoordinatorMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user

        if user.user_role != 'coordinator':
            raise ValidationError({'error': 'User must be an OJT Coordinator.'})

        try:
            coordinator = OJTCoordinator.objects.select_related('program').get(user=user)
        except OJTCoordinator.DoesNotExist:
            raise ValidationError({'error': 'Coordinator profile not found.'})

        applicants = Applicant.objects.filter(program=coordinator.program)

        pending_count = 0
        accepted_count = 0

        for applicant in applicants:
            if applicant.applications.filter(status='Accepted').exists():
                accepted_count += 1
            else:
                pending_count += 1

        return Response({
            "accepted_applicants": accepted_count,
            "pending_applicants": pending_count,
            "total_applicants": accepted_count + pending_count,
        })


# Students Requesting Practicum List -- KC
@ojt_management_tag
class GetRequestPracticumListView(CoordinatorMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsCoordinator]
    serializer_class = GetApplicantSerializer

    filter_backends = [filters.SearchFilter]

    search_fields = [
        'first_name'
        , 'last_name'
        , 'user__email'
    ]

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        return Applicant.objects.filter(
            program=coordinator.program
            , user__status__in=['Active']
            , in_practicum='Pending'
            , enrollment_record__isnull=False
        ).select_related('user')

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            if not queryset:
                return Response({'message': 'No students found.'})

            return super().list(request, *args, **kwargs)
        except Exception as e:
            raise ValidationError({'error': f'An error occurred while retrieving students: {str(e)}'})


# Applicant: Request for Practicum -- KC
@ojt_management_tag
class RequestPracticumView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated, IsApplicant]
    queryset = Applicant.objects.all()
    serializer_class = UpdatePracticumStatusSerializer

    no_active_coordinator = False

    def get_object(self):
        try:
            return self.request.user.applicant
        except Applicant.DoesNotExist:
            raise ValidationError({'error': 'Applicant account not found.'})

    def build_email_context(self, applicant, coordinator):
        applicant_fullname = f"{applicant.first_name} {applicant.last_name}"
        coordinator_fullname = f"{coordinator.first_name} {coordinator.last_name}"
        context = {
            'subject': "New Practicum Request ",
            'email_message': (
                f'Dear <strong>{coordinator_fullname}</strong>,<br><br>'
                f'A new practicum request has been submitted by <strong>{applicant_fullname}</strong>.<br><br>'
                'Please log in to Between IMS to review the request.<br><br>'
                'Best regards,<br><strong>Between Team</strong>'
            )
        }
        return context

    def get_serializer_context(self):
        applicant = self.get_object()
        try:
            coordinator = OJTCoordinator.objects.get(program=applicant.program, user__status__in=['Active'])
            email_context = self.build_email_context(applicant, coordinator)
            return {**email_context, 'coordinator': coordinator, 'recipient_list': [coordinator.user.email]}
        except OJTCoordinator.DoesNotExist:
            self.no_active_coordinator = True
            return {}

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        applicant = request.user.applicant

        if applicant.in_practicum == 'Yes':
            return Response({'error': 'Action not allowed. Student is already in practicum.'})

        enrollment_record_data = request.data.get('enrollment_record')
        if not enrollment_record_data:
            raise ValidationError({'error': 'Enrollment record is required.'})

        enrollment_record_file = request.FILES.get('enrollment_record')
        if (enrollment_record_file and applicant.enrollment_record and applicant.enrollment_record !=
                enrollment_record_file):
            applicant.enrollment_record.delete(save=False)

        if enrollment_record_file:
            try:
                validate_file_size(enrollment_record_file)
            except ValidationError as e:
                raise ValidationError({'enrollment_record': e.detail})

        er_serializer = EnrollmentRecordSerializer(instance=applicant, data=request.data, partial=True)
        er_serializer.is_valid(raise_exception=True)
        try:
            er_serializer.save()
        except Exception as e:
            raise ValidationError(
                {'error': f'An error occurred while saving the enrollment record: {str(e)}. Please try again.'},
            )

        serializer = self.get_serializer(instance=applicant, data={'in_practicum': 'Pending'}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if self.no_active_coordinator:
            return Response({
                'message': (
                    'Practicum status changed to Pending, but no active OJT Coordinator is assigned to your program. '
                    'Please contact your school administrator.'
                )
            }, status=status.HTTP_200_OK)

        return Response({'message': 'Practicum Request Sent.'}, status=status.HTTP_200_OK)


# View Enrollment Record -- KC
@ojt_management_tag
class GetEnrollmentRecordView(CoordinatorMixin, generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EnrollmentRecordSerializer

    def get_object(self):
        user = self.request.query_params.get('user')
        if not user:
            raise ValidationError({"error": "Query parameter 'user' is required."})

        coordinator = self.get_coordinator_or_403(self.request.user)
        try:
            applicant = Applicant.objects.get(
                user__user_id=user
                , program=coordinator.program
                , user__status__in=['Active']
            )
        except Applicant.DoesNotExist:
            raise ValidationError({"error": f"No student found for user: {user}"})

        if not applicant.enrollment_record:
            raise ValidationError({"error": "No enrollment record found for student."})

        return applicant


# Approve Practicum Request -- KC
@ojt_management_tag
class ApprovePracticumRequestView(CoordinatorMixin, generics.UpdateAPIView):
    permission_classes = [IsAuthenticated, IsCoordinator]
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

    def build_email_context(self, applicant):
        fullname = f"{applicant.first_name} {applicant.last_name}"
        context = {
            'subject': "Practicum Request Approved",
            'email_message': (
                f"Dear <strong>{fullname}</strong>,<br><br>"
                "Your practicum request has been approved! We wish you great success.<br><br>"
                "Best regards,<br><strong>Between Team</strong>"
            )
        }
        return context

    def get_serializer_context(self):
        applicant = self.get_object()
        coordinator = self.get_coordinator_or_403(self.request.user)

        email_context = self.build_email_context(applicant)

        return {**email_context, 'coordinator': coordinator, 'recipient_list': [applicant.user.email]}

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        applicant = self.get_object()

        if applicant.in_practicum != 'Pending':
            return Response({'error': 'Action not allowed. Student has not requested to be in practicum.'})

        if not applicant.enrollment_record:
            return Response({'error': 'Action not allowed. Student has not submitted enrollment record.'})

        serializer = self.get_serializer(instance=applicant, data={'in_practicum': 'Yes'}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        log_coordinator_action(
            user=self.request.user,
            action="Approved Practicum Request",
            action_type='change',
            obj=applicant,
            details=f"Approved Practicum Request of: {applicant.user.email}"
        )

        return Response({'message': 'Practicum request approved successfully.'}, status=status.HTTP_200_OK)


# Reject Practicum Request -- KC
@ojt_management_tag
class RejectPracticumRequestView(CoordinatorMixin, generics.UpdateAPIView):
    permission_classes = [IsAuthenticated, IsCoordinator]
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

    def build_email_context(self, applicant, reason):
        fullname = f"{applicant.first_name} {applicant.last_name}"
        context = {
            'subject': "Practicum Request Rejected",
            'email_message': (
                f'Dear <strong>{fullname}</strong>,<br><br>'
                'We regret to inform you that your practicum request has been rejected.<br><br>'
                f'<strong>Reason:</strong> {reason}<br><br>'
                'Please contact your program coordinator for more details.<br><br>'
                'Best regards,<br><strong>Between Team</strong>'
            )
        }
        return context

    def get_serializer_context(self):
        applicant = self.get_object()
        coordinator = self.get_coordinator_or_403(self.request.user)
        reason = self.request.data['reason']
        email_context = self.build_email_context(applicant, reason=reason)

        return {**email_context, 'coordinator': coordinator, 'recipient_list': [applicant.user.email]}

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        applicant = self.get_object()

        if applicant.in_practicum != 'Pending':
            return Response({'error': 'Action not allowed. Student has not requested to be in practicum.'})

        if not applicant.enrollment_record:
            return Response({'error': 'Action not allowed. Student has not submitted enrollment record.'})

        reason = request.data.get('reason')
        if not reason:
            return Response({'error': 'A reason is required to reject a practicum request.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(instance=applicant, data={'in_practicum': 'No'}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        log_coordinator_action(
            user=self.request.user,
            action="Rejected Practicum Request",
            action_type='change',
            obj=applicant,
            details=f"Rejected Practicum Request of: {applicant.user.email}"
        )

        return Response({'message': 'Practicum request rejected successfully.'}, status=status.HTTP_200_OK)


#  End Student's Practicum -- KC
@ojt_management_tag
class EndPracticumView(CoordinatorMixin, generics.UpdateAPIView):
    permission_classes = [IsAuthenticated, IsCoordinator]
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

    def build_email_context(self, applicant):
        fullname = f"{applicant.first_name} {applicant.last_name}"
        context = {
            'subject': "Practicum Ended",
            'email_message': (
                f'Dear <strong>{fullname}</strong>,<br><br>'
                f'Your practicum has been successfully marked as ended.<br><br>'
                'If you have any questions, please contact your coordinator.<br><br>'
                'Best regards,<br><strong>Between Team</strong>'
            )
        }
        return context

    def get_serializer_context(self):
        applicant = self.get_object()
        coordinator = self.get_coordinator_or_403(self.request.user)

        email_context = self.build_email_context(applicant)

        return {**email_context, 'coordinator': coordinator, 'recipient_list': [applicant.user.email]}

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        applicant = self.get_object()

        if applicant.in_practicum != 'Yes':
            return Response({'error': 'Action not allowed. Student is not currently in practicum.'})

        if not applicant.enrollment_record:
            return Response({'error': 'Action not allowed. Student has not submitted enrollment record.'})

        """
        applicant.enrollment_record.delete(save=False)
        applicant.enrollment_record = None
        applicant.save(update_fields=['enrollment_record'])
        """

        serializer = self.get_serializer(instance=applicant, data={'in_practicum': 'No'}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        log_coordinator_action(
            user=self.request.user,
            action="Ended Practicum",
            action_type='change',
            obj=applicant,
            details=f"Ended Practicum of: {applicant.user.email}"
        )

        return Response({'message': 'Practicum was ended successfully.'}, status=status.HTTP_200_OK)


class ResetPracticumView(CoordinatorMixin, generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsCoordinator]
    queryset = Applicant.objects.all()
    serializer_class = UpdatePracticumStatusSerializer

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        queryset = Applicant.objects.filter(program=coordinator.program, in_practicum='Yes')
        return queryset

    def build_email_context(self, applicant):
        fullname = f"{applicant.first_name} {applicant.last_name}"
        context = {
            'subject': "Practicum Ended",
            'email_message': (
                f'<strong>{fullname}</strong>\'s practicum has been successfully marked as ended.<br><br>'
                'If you have any questions, please contact your coordinator.<br><br>'
                'Best regards,<br><strong>Between Team</strong>'
            )
        }
        return context

    def post(self, request, *args, **kwargs):
        applicants = self.get_queryset()
        if not applicants:
            return Response({'message': 'No students are currently in practicum.'}, status=status.HTTP_200_OK)

        updated_count = 0
        failed_updates = []

        for applicant in applicants:
            with transaction.atomic():
                if not applicant.enrollment_record:
                    failed_updates.append({
                        'user_id': applicant.user.user_id,
                        'error': 'No enrollment record found for student.'
                    })
                    continue

                email_context = self.build_email_context(applicant)
                coordinator = self.get_coordinator_or_403(request.user)
                serializer_context = {
                    **email_context,
                    'coordinator': coordinator,
                    'recipient_list': [applicant.user.email]
                }

                serializer = self.get_serializer(
                    instance=applicant,
                    data={'in_practicum': 'No'},
                    partial=True,
                    context=serializer_context
                )

                try:
                    serializer.is_valid(raise_exception=True)
                    serializer.save()
                    updated_count += 1

                    log_coordinator_action(
                        user=self.request.user,
                        action="Practicum Reset",
                        action_type='change',
                        obj=applicant,
                        details=f"Practicum was Reset for this Term."
                    )

                except Exception as e:
                    failed_updates.append({
                        'user_id': applicant.user.user_id,
                        'error': str(e)
                    })

        response_data = {
            'message': f'Successfully ended practicum for {updated_count} students.',
        }

        if failed_updates:
            response_data['failures'] = failed_updates

        return Response(response_data, status=status.HTTP_200_OK)

# endregion


# region Endorsement Management -- PAUL

@ojt_management_tag
class RespondedEndorsementListView(CoordinatorMixin, generics.ListAPIView):
    serializer_class = EndorsementDetailSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]

    search_fields = [
        'application__applicant__user__email',
        'application__applicant__first_name',
        'application__applicant__last_name',
        'application__applicant__middle_initial',
        'application__internship_posting__company__company_name',
        'application__internship_posting__internship_position',
        'application__internship_posting__person_in_charge__name',
    ]

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        return Endorsement.objects.filter(
            program_id=coordinator.program
        ).exclude(status__in=['Pending', 'Deleted'])


@ojt_management_tag
class EndorsementDetailView(CoordinatorMixin, generics.ListAPIView):
    serializer_class = EndorsementDetailSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]

    search_fields = [
        'application__applicant__user__email',
        'application__applicant__first_name',
        'application__applicant__last_name',
        'application__applicant__middle_initial',
        'application__internship_posting__company__company_name',
        'application__internship_posting__internship_position',
        'application__internship_posting__person_in_charge__name',
    ]

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)

        return Endorsement.objects.filter(
            program_id=coordinator.program_id,
            status='Pending'
        )


@ojt_management_tag
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


@ojt_management_tag
class UpdateEndorsementView(CoordinatorMixin, generics.GenericAPIView):
    serializer_class = UpdateEndorsementSerializer
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request, *args, **kwargs):
        endorsement_id = request.query_params.get('endorsement_id')
        endorsement_status = request.data.get('status')
        comments = request.data.get('comments', '')

        if not endorsement_id:
            raise ValidationError({"endorsement_id": "This query parameter is required."})

        try:
            uuid.UUID(endorsement_id)
        except (ValueError, TypeError):
            raise ValidationError({"endorsement_id": "This is not a valid UUID."})

        if endorsement_status not in ['Approved', 'Rejected']:
            raise ValidationError({"status": "Status must be either 'Approved' or 'Rejected'."})

        coordinator = self.get_coordinator_or_403(request.user)

        try:
            endorsement = Endorsement.objects.get(endorsement_id=endorsement_id)
        except Endorsement.DoesNotExist:
            raise ValidationError({'error': '"Endorsement not found."'})

        if endorsement.program_id != coordinator.program:
            raise PermissionDenied("You do not have permission to update this endorsement.")

        if endorsement.status != 'Pending':
            raise ValidationError({"status": "Only endorsements with 'Pending' status can be updated."})

        if endorsement_status == 'Rejected' and not comments:
            raise ValidationError({"comments": "Comments are required when rejecting an endorsement."})

        with transaction.atomic():
            endorsement.status = endorsement_status
            endorsement.comments = comments if endorsement_status == 'Rejected' else None
            endorsement.save()

            coordinator.endorsements_responded = (coordinator.endorsements_responded or 0) + 1
            coordinator.save()

        applicant_email = endorsement.application.applicant.user.email
        applicant = endorsement.application.applicant
        company_name = endorsement.application.internship_posting.company.company_name
        internship_position = endorsement.application.internship_posting.internship_position
        applicant_name = (
                applicant.first_name +
                (' ' + applicant.middle_initial if applicant.middle_initial else '') +
                ' ' + applicant.last_name
        )

        coordinator_name = (
                coordinator.first_name +
                (' ' + coordinator.middle_initial if coordinator.middle_initial else '') +
                ' ' + coordinator.last_name
        )

        if endorsement_status == 'Approved':

            if not coordinator.program_logo or not coordinator.signature:
                raise ValidationError({
                    "error": "Your program logo and signature must be uploaded before approving an "
                             "endorsement."
                })

            subject = f"Your Endorsement Has Been Approved"
            message_html = f"""
            <div>
                <p>Dear <strong>{applicant_name}</strong>,</p>
                <p>Your endorsement for the internship position 
                   <strong>{internship_position}</strong> at <strong>{company_name}</strong> has been <strong>approved</strong>.</p>
                <p>You may now proceed with your internship application process with the company.</p>
                <p>
                 Best regards, <strong>
                 <br><br>{coordinator_name}
                 <br>Practicum Coordinator - {coordinator.program}
                 <br>{coordinator.user.email} </strong>
                </p>
            </div>
            """

            program_logo_data = base64.b64encode(coordinator.program_logo.read()).decode('utf-8')
            coordinator.program_logo.seek(0)
            signature_data = base64.b64encode(coordinator.signature.read()).decode('utf-8')
            coordinator.signature.seek(0)

            html_string = render_to_string("endorsement_letter_template.html", {
                "endorsement": endorsement,
                "coordinator": coordinator,
                "today": date.today(),
                "program_logo_data": program_logo_data,
                "signature_data": signature_data,
            })

            html_file = io.BytesIO(html_string.encode('utf-8'))
            html_file.name = 'endorsement.html'

            try:
                pdf_response = requests.post(
                    f'{WEASYPRINT_SERVICE_URL}',
                    files={'html': ('endorsement.html', html_file, 'text/html')},
                    timeout=15
                )
                pdf_response.raise_for_status()
            except requests.RequestException as e:
                raise ValidationError({"error": f"WeasyPrint PDF generation failed: {str(e)}"})

            email = EmailMessage(
                subject=subject,
                body=message_html,
                from_email=formataddr((
                    f'{coordinator_name}',
                    'between_internships@gmail.com')),
                to=[applicant_email, coordinator.user.email],
                reply_to=['no-reply@betweeninternships.com']
            )
            email.content_subtype = 'html'
            email.attach(
                f"endorsement_{endorsement.endorsement_id}.pdf",
                pdf_response.content,
                'application/pdf'
            )
            email.send(fail_silently=False)

            log_coordinator_action(
                user=request.user,
                action="Endorsement Approved",
                action_type="change",
                obj=endorsement,
                details=f"Approved endorsement for {applicant.user.email} - {internship_position} at {company_name}"
            )

        else:
            subject = f"Your Endorsement Has Been Rejected"
            message_html = f"""
            <div>
                <p>Dear <strong>{applicant_name}</strong>,</p>
                <p>Your endorsement for the internship position 
                   <strong>{internship_position}</strong> at <strong>{company_name}</strong> has been <strong>rejected</strong>.</p>
                <p><strong>Comments:</strong><br>{comments.replace('\n', '<br>')}</p>
                 <p>You may resubmit your endorsement request after addressing the comments provided above.</p>\
                 <p>
                Best regards, <strong>
                 <br><br>{coordinator_name}
                 <br>Practicum Coordinator - {coordinator.program}
                 <br>{coordinator.user.email} </strong> 
                </p>
            </div>
            """

            email = EmailMessage(
                subject=subject,
                body=message_html,
                from_email=formataddr(
                    (f'{coordinator_name}',
                     'between_internships@gmail.com')),
                to=[applicant_email],
                reply_to=['no-reply@betweeninternships.com']
            )
            email.content_subtype = 'html'
            email.send(fail_silently=False)

            log_coordinator_action(
                user=request.user,
                action="Endorsement Rejected",
                action_type="change",
                obj=endorsement,
                details=f"Rejected endorsement for {applicant.user.email} - {internship_position} at {company_name}"
            )

        serializer = self.get_serializer(endorsement)
        return Response(serializer.data, status=status.HTTP_200_OK)


@ojt_management_tag
class GenerateEndorsementPDFView(CoordinatorMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if not hasattr(user, 'ojtcoordinator'):
            raise PermissionDenied("Only OJT Coordinators can generate endorsement previews.")

        coordinator = user.ojtcoordinator

        if not coordinator.program_logo or not coordinator.signature:
            return Response({
                "message":
                    "Your program logo and signature must be uploaded before generating an endorsement preview PDF."
            })

        program_logo_data = base64.b64encode(coordinator.program_logo.read()).decode('utf-8')
        coordinator.program_logo.seek(0)

        signature_data = base64.b64encode(coordinator.signature.read()).decode('utf-8')
        coordinator.signature.seek(0)

        html_string = render_to_string("endorsement_letter_template_preview.html", {
            "coordinator": coordinator,
            "today": date.today(),
            "program_logo_data": program_logo_data,
            "signature_data": signature_data,
        })

        html_file = io.BytesIO(html_string.encode('utf-8'))
        html_file.name = 'endorsement.html'

        try:
            response = requests.post(
                f'{WEASYPRINT_SERVICE_URL}',
                files={'html': ('endorsement.html', html_file, 'text/html')},
                timeout=15
            )
            response.raise_for_status()
        except requests.RequestException as e:
            return Response({"error": f"WeasyPrint service error: {str(e)}"}, status=500)

        return HttpResponse(
            response.content,
            content_type='application/pdf',
            headers={'Content-Disposition': 'attachment; filename=endorsement_preview.pdf'}
        )

# endregion


@ojt_management_tag
class ChangeLogoAndSignatureView(CoordinatorMixin, generics.UpdateAPIView):
    permission_classes = [IsAuthenticated, IsCoordinator]
    serializer_class = OJTCoordinatorDocumentSerializer

    def get_object(self):
        user = self.request.user
        if user.user_role != 'coordinator':
            raise ValidationError({'error': 'User must be an OJT Coordinator.'})
        return OJTCoordinator.objects.get(user=user)

    def perform_update(self, serializer):
        instance = serializer.save()
        log_coordinator_action(
            user=self.request.user,
            action="Uploaded Logo and Signature",
            action_type="change",
            obj=instance,
            details="Coordinator uploaded a new program logo and/or signature."
        )


class CoordinatorAuditLogView(CoordinatorMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        user = self.request.user
        if user.user_role != 'coordinator':
            raise ValidationError({'error': 'User must be an OJT Coordinator.'})

        return AuditLog.objects.filter(user=user).order_by('-timestamp')[:10]


class PartneredCompaniesMetricsView(CoordinatorMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SchoolPartnershipSerializer

    def get_queryset(self):
        user = self.request.user
        if user.user_role != 'coordinator':
            raise ValidationError({'error': 'User must be an OJT Coordinator.'})

        coordinator = OJTCoordinator.objects.select_related('department__school').get(user=user)
        return SchoolPartnershipList.objects.filter(school=coordinator.department.school)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        total = len(queryset)
        return Response({'total_partnerships': total})


class TotalSearchingForPracticumMetricsView(CoordinatorMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GetApplicantSerializer

    def get_queryset(self):
        user = self.request.user
        if user.user_role != 'coordinator':
            raise ValidationError({'error': 'User must be an OJT Coordinator.'})

        coordinator = OJTCoordinator.objects.select_related('program').get(user=user)
        return Applicant.objects.filter(program=coordinator.program).exclude(program__isnull=True)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        total = len(queryset)
        return Response({'total_searching_for_practicum': total})


class EndorsementRequestMetricView(CoordinatorMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EndorsementListSerializer

    def get_queryset(self):
        user = self.request.user
        if user.user_role != 'coordinator':
            raise ValidationError({'error': 'User must be an OJT Coordinator.'})

        coordinator = OJTCoordinator.objects.select_related('program').get(user=user)
        return Endorsement.objects.filter(
            program_id=coordinator.program_id
        ).exclude(status__in=['Approved', 'Rejected', 'Deleted'])

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        total = len(queryset)
        return Response({'total_endorsement_requests': total})


class EndorsementsRespondedMetricView(CoordinatorMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user

        if user.user_role != 'coordinator':
            raise ValidationError({'error': 'User must be an OJT Coordinator.'})

        try:
            coordinator = OJTCoordinator.objects.get(user=user)
        except OJTCoordinator.DoesNotExist:
            raise ValidationError({'error': 'Coordinator profile not found.'})

        data = {
            "endorsements_responded": coordinator.endorsements_responded
        }
        return Response(data)






