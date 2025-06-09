import uuid
from datetime import date
from email.utils import formataddr

import requests
from django.core.files.base import ContentFile
from django.core.mail import send_mail, EmailMessage
from django.db import transaction
from django.http import HttpResponse
from django.template.loader import render_to_string
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
    permission_class = [IsAuthenticated, IsCoordinator]

    def get_coordinator_or_403(self, user):
        try:
            return OJTCoordinator.objects.get(user=user)
        except OJTCoordinator.DoesNotExist:
            raise PermissionDenied('User is not an OJT Coordinator. Access denied.')


@ojt_management_tag
# School Partnerships
# region School Partnerships -- KC
class SchoolPartnershipListView(CoordinatorMixin, generics.ListAPIView):
    serializer_class = SchoolPartnershipSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['company__company_name']

    def get_queryset(self):
        coordinator = self.get_coordinator_or_403(self.request.user)
        return SchoolPartnershipList.objects.filter(school=coordinator.program.department.school).select_related(
            'company', 'company__user')


# endregion

# region Student List -- KC


@ojt_management_tag
class ApplicantListView(CoordinatorMixin, generics.ListAPIView):
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


# endregion

# region Practicum Management


@ojt_management_tag
# Students In Practicum List -- KC
class GetPracticumStudentListView(CoordinatorMixin, generics.ListAPIView):
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


@ojt_management_tag
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

        applicant.enrollment_record.delete(save=False)
        applicant.enrollment_record = None
        applicant.save(update_fields=['enrollment_record'])

        return super().update(request, *args, **kwargs)


@ojt_management_tag
# Students Requesting Practicum List -- KC
class GetRequestPracticumListView(CoordinatorMixin, generics.ListAPIView):
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
