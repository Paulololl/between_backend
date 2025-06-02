import uuid
from datetime import date
from email.utils import formataddr

from django.core.mail import send_mail, EmailMessage
from django.db import transaction
from django.http import HttpResponse
from django.template.loader import render_to_string
from rest_framework.exceptions import  PermissionDenied, ValidationError
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from weasyprint import HTML

from cea_management import serializers
from client_application.models import Endorsement
from user_account.permissions import IsApplicant
from .permissions import IsCoordinator
from user_account.models import OJTCoordinator, Applicant
from user_account.serializers import GetApplicantSerializer
from cea_management.models import SchoolPartnershipList
from cea_management.serializers import SchoolPartnershipSerializer
from . import serializers as ojt_serializers
from .serializers import EndorsementListSerializer, EndorsementDetailSerializer, RequestEndorsementSerializer, \
    UpdateEndorsementSerializer


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
                from_email=formataddr((f'{coordinator.first_name} {coordinator.middle_initial} {coordinator.last_name}',
                                       'between_internships@gmail.com')),
                to=[applicant_email],
                reply_to=['no-reply@betweeninternships.com']
            )
            email.content_subtype = 'html'
            email.send(fail_silently=False)

        serializer = self.get_serializer(endorsement)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GenerateEndorsementPDFView(CoordinatorMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        endorsement_id = request.query_params.get('endorsement_id')
        if not endorsement_id:
            return Response({'error': '"endorsement_id is required", status=400'})

        try:
            endorsement = (Endorsement.objects.select_related('application', 'program_id').get
                           (endorsement_id=endorsement_id))
        except Endorsement.DoesNotExist:
            raise ValidationError("Endorsement not found.")

        user = request.user
        if hasattr(user, 'applicant') and endorsement.application.applicant != user.applicant:
            raise PermissionDenied("You don't have access to this endorsement.")
        elif hasattr(user, 'ojtcoordinator') and user.ojtcoordinator.program != endorsement.program_id:
            raise PermissionDenied("You don't manage this program's endorsements.")

        html_string = render_to_string("endorsement_letter_template.html", {
            "endorsement": endorsement,
            "coordinator": user.ojtcoordinator if hasattr(user, 'ojtcoordinator') else None,
            "today": date.today()
        })

        html = HTML(string=html_string)
        pdf = html.write_pdf()

        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename=endorsement_{endorsement_id}.pdf'
        return response





