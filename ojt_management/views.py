import uuid
from datetime import date
from email.utils import formataddr

import requests
from django.core.files.base import ContentFile
from django.core.mail import send_mail, EmailMessage
from django.db import transaction
from django.http import HttpResponse
from django.template.loader import render_to_string
from django_extensions.management.commands.export_emails import full_name
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework import generics, status, filters, request
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from weasyprint import HTML

from between_ims import settings
from cea_management import serializers
from client_application.models import Endorsement
from user_account.permissions import IsCoordinator, IsApplicant
from user_account.models import OJTCoordinator, Applicant
from user_account.serializers import GetApplicantSerializer, OJTCoordinatorDocumentSerializer
from cea_management.models import SchoolPartnershipList
from cea_management.serializers import SchoolPartnershipSerializer
from .serializers import EndorsementDetailSerializer, RequestEndorsementSerializer, \
    UpdatePracticumStatusSerializer, UpdateEndorsementSerializer, EnrollmentRecordSerializer

ojt_management_tag = extend_schema(tags=["ojt_management"])


class CoordinatorMixin:
    def get_coordinator_or_403(self, user):
        try:
            return OJTCoordinator.objects.get(user=user)
        except OJTCoordinator.DoesNotExist:
            raise PermissionDenied('User is not an OJT Coordinator. Access denied.')

# region School Partnerships -- KC
@ojt_management_tag
class SchoolPartnershipListView(CoordinatorMixin, generics.ListAPIView):
    permission_class = [IsAuthenticated, IsCoordinator]
    serializer_class = SchoolPartnershipSerializer

    filter_backends = [filters.SearchFilter]
    search_fields = ['company__company_name']

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        return SchoolPartnershipList.objects.filter(school=coordinator.program.department.school).select_related(
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
        queryset = Applicant.objects.filter(program=coordinator.program, user__status__in=['Active'])

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

    search_fields = [
        'first_name'
        , 'last_name'
        , 'user__email'
    ]

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        queryset = Applicant.objects.filter(
            program=coordinator.program
            , user__status__in=['Active']
            , in_practicum='Yes'
            , enrollment_record__isnull=False
        ).select_related('user')

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
            program__department__school=coordinator.program.department.school
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
        except OJTCoordinator.DoesNotExist:
            raise ValidationError({'error': 'No OJT Coordinator is currently assigned to this program. Please contact '
                                            'your school administrator for assistance.'})

        email_context = self.build_email_context(applicant, coordinator)

        return {**email_context, 'coordinator': coordinator, 'recipient_list': [coordinator.user.email]}

    def update(self, request, *args, **kwargs):
        applicant = request.user.applicant

        if applicant.in_practicum == 'Yes':
            return Response({'error': 'Action not allowed. Student is already in practicum.'})

        enrollment_record_data = request.data.get('enrollment_record')
        if not enrollment_record_data:
            raise ValidationError({'error': 'Enrollment record is required.'})

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

    def update(self, request, *args, **kwargs):
        applicant = self.get_object()

        if applicant.in_practicum != 'Pending':
            return Response({'error': 'Action not allowed. Student has not requested to be in practicum.'})

        if not applicant.enrollment_record:
            return Response({'error': 'Action not allowed. Student has not submitted enrollment record.'})

        serializer = self.get_serializer(instance=applicant, data={'in_practicum': 'Yes'}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

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
            if not applicant.enrollment_record:
                failed_updates.append({
                    'user_id': applicant.user.user_id,
                    'error': 'No enrollment record found for student.'
                })

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
            except Exception as e:
                failed_updates.append({
                    'user_id': applicant.user.user_id,
                    'error': str(e)
                })

        return Response({
            'message': f'Successfully ended practicum for {updated_count} students.',
            'failures': failed_updates
        }, status=status.HTTP_200_OK)

# endregion


# region Endorsement Management -- PAUL

@ojt_management_tag
class RespondedEndorsementListView(CoordinatorMixin, generics.ListAPIView):
    serializer_class = EndorsementDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        return Endorsement.objects.filter(
            program_id=coordinator.program
        ).exclude(status__in=['Pending', 'Deleted'])


@ojt_management_tag
class EndorsementDetailView(CoordinatorMixin, generics.ListAPIView):
    serializer_class = EndorsementDetailSerializer
    permission_classes = [IsAuthenticated]

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

            applicant_email = endorsement.application.applicant.user.email
            applicant = endorsement.application.applicant
            company_name = endorsement.application.internship_posting.company.company_name
            internship_position = endorsement.application.internship_posting.internship_position

            if endorsement_status == 'Approved':

                if not coordinator.program_logo or not coordinator.signature:
                    raise ValidationError({
                        "error": "Your program logo and signature must be uploaded before approving an "
                                 "endorsement."
                    })

                subject = f"Your Endorsement Has Been Approved"
                message_html = f"""
                <div>
                    <p>Dear <strong>{applicant.first_name} {applicant.middle_initial} {applicant.last_name}</strong>,</p>
                    <p>Your endorsement for the internship position 
                       <strong>{internship_position}</strong> at <strong>{company_name}</strong> has been <strong>approved</strong>.</p>
                    <p>
                     Best regards, <br> <strong>
                     <br>{coordinator.first_name} {coordinator.middle_initial} {coordinator.last_name}
                     <br>Practicum Coordinator - {coordinator.program}
                     <br>{coordinator.user.email} </strong>
                    </p>
                </div>
                """

                html_string = render_to_string("endorsement_letter_template.html", {
                    "endorsement": endorsement,
                    "coordinator": coordinator,
                    "today": date.today()
                })

                pdf_bytes = HTML(string=html_string).write_pdf()

                email = EmailMessage(
                    subject=subject,
                    body=message_html,
                    from_email=formataddr((
                        f'{coordinator.first_name} {coordinator.middle_initial} {coordinator.last_name}',
                        'between_internships@gmail.com')),
                    to=[applicant_email, coordinator.user.email],
                    reply_to=['no-reply@betweeninternships.com']
                )
                email.content_subtype = 'html'
                email.attach(f"endorsement_{endorsement.endorsement_id}.pdf", pdf_bytes, 'application/pdf')
                email.send(fail_silently=False)

            else:
                subject = f"Your Endorsement Has Been Rejected"
                message_html = f"""
                <div>
                    <p>Dear <strong>{applicant.first_name} {applicant.middle_initial} {applicant.last_name}</strong>,</p>
                    <p>Your endorsement for the internship position 
                       <strong>{internship_position}</strong> at <strong>{company_name}</strong> has been <strong>rejected</strong>.</p>
                    <p><strong>Comments:</strong><br>{comments.replace('\n', '<br>')}</p>
                     <p>
                    Best regards, <br> <strong>
                     <br>{coordinator.first_name} {coordinator.middle_initial} {coordinator.last_name}
                     <br>Practicum Coordinator - {coordinator.program}
                     <br>{coordinator.user.email} </strong> 
                    </p>
                </div>
                """

                email = EmailMessage(
                    subject=subject,
                    body=message_html,
                    from_email=formataddr(
                        (f'{coordinator.first_name} {coordinator.middle_initial} {coordinator.last_name}',
                         'between_internships@gmail.com')),
                    to=[applicant_email],
                    reply_to=['no-reply@betweeninternships.com']
                )
                email.content_subtype = 'html'
                email.send(fail_silently=False)

        serializer = self.get_serializer(endorsement)
        return Response(serializer.data, status=status.HTTP_200_OK)


@ojt_management_tag
class GenerateEndorsementPDFView(CoordinatorMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Ensure user is an OJT Coordinator
        if not hasattr(user, 'ojtcoordinator'):
            raise PermissionDenied("Only OJT Coordinators can generate endorsement previews.")

        coordinator = user.ojtcoordinator

        if not coordinator.program_logo or not coordinator.signature:
            return Response({
                "message":
                    "Your program logo and signature must be uploaded before generating an endorsement preview PDF."
            })

        html_string = render_to_string("endorsement_letter_template_preview.html", {
            "coordinator": coordinator,
            "today": date.today(),
        })

        pdf_bytes = HTML(string=html_string).write_pdf()

        return HttpResponse(
            pdf_bytes,
            content_type='application/pdf',
            headers={'Content-Disposition': 'attachment; filename=endorsement_preview.pdf'}
        )

# endregion


@ojt_management_tag
class ChangeLogoAndSignatureView(CoordinatorMixin, generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OJTCoordinatorDocumentSerializer

    def get_object(self):
        user = self.request.user

        try:
            return OJTCoordinator.objects.get(user=user)
        except OJTCoordinator.DoesNotExist:
            raise ValidationError({"error": "OJT Coordinator not found for the authenticated user."})

