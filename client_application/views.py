from email.utils import formataddr

from django.core.mail import send_mail, EmailMessage
from django.db import transaction
from django.db.models import Q, F
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.generics import ListAPIView, CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from client_application.models import Application, Notification, Endorsement
from client_application.serializers import ApplicationListSerializer, ApplicationDetailSerializer, \
    NotificationSerializer, UpdateApplicationSerializer, RequestDocumentSerializer, \
    SendDocumentSerializer, ApplicationSerializer
from client_matching.functions import run_internship_matching
from client_matching.models import InternshipRecommendation
from client_matching.serializers import InternshipMatchSerializer
from client_matching.utils import reset_recommendations_and_tap_count
from user_account.models import OJTCoordinator
from user_account.permissions import IsCompany, IsApplicant

client_application_tag = extend_schema(tags=["client_application"])


@client_application_tag
class ApplicationListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ApplicationListSerializer

    def get_queryset(self):
        user = self.request.user

        if user.user_role == 'applicant':
            queryset = Application.objects.filter(applicant__user=user).exclude(applicant_status='Deleted')
        elif user.user_role == 'company':
            queryset = (Application.objects.filter(internship_posting__company__user=user).exclude
                        (company_status='Deleted'))
        else:
            return Application.objects.none()

        application_status = self.request.query_params.get('application_status')
        allowed_status = ['Onboarding', 'Pending', 'Rejected', 'Dropped', 'Accepted']
        if application_status:
            if application_status not in allowed_status:
                raise serializers.ValidationError({'error': 'Invalid application status'})
            queryset = queryset.filter(status__iexact=application_status)

        view_status = self.request.query_params.get('view_status')
        allowed_view_status = ['Read', 'Unread']
        if view_status:
            if view_status not in allowed_view_status:
                raise serializers.ValidationError({'error': 'Invalid view status'})
            if view_status == 'Read':
                if user.user_role == 'applicant':
                    queryset = queryset.filter(applicant_status='Read')
                elif user.user_role == 'company':
                    queryset = queryset.filter(company_status='Read')
            elif view_status == 'Unread':
                if user.user_role == 'applicant':
                    queryset = queryset.filter(applicant_status='Unread')
                elif user.user_role == 'company':
                    queryset = queryset.filter(company_status='Unread')

        date_order = self.request.query_params.get('date_order')
        allowed_date_order = ['Newest', 'Oldest']
        if date_order:
            if date_order not in allowed_date_order:
                raise serializers.ValidationError({'error': 'Invalid date order'})
            if date_order == 'Newest':
                queryset = queryset.order_by('-application_date')
            elif date_order == 'Oldest':
                queryset = queryset.order_by('application_date')

        internship_position = self.request.query_params.get('internship_position')
        if user.user_role in ['company', 'applicant'] and internship_position:
            queryset = queryset.filter(
                internship_posting__internship_position__iexact=internship_position
            )

        company_name = self.request.query_params.get('company_name')
        if user.user_role == 'applicant' and company_name:
            queryset = queryset.filter(internship_posting__company__company_name__icontains=company_name)

        applicant_name = self.request.query_params.get('applicant_name')
        if user.user_role == 'company' and applicant_name:
            name_parts = applicant_name.strip().split()

            queryset = queryset.filter(
                Q(applicant__first_name__icontains=applicant_name) |
                Q(applicant__last_name__icontains=applicant_name)
            )

            if len(name_parts) > 1:
                queryset = queryset.union(
                    queryset.model.objects.filter(
                        Q(applicant__first_name__icontains=name_parts[0],
                          applicant__last_name__icontains=' '.join(name_parts[1:])) |
                        Q(applicant__last_name__icontains=name_parts[-1],
                          applicant__first_name__icontains=' '.join(name_parts[:-1]))
                    )
                )

        return queryset


@client_application_tag
class ApplicationDetailView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ApplicationDetailSerializer

    def get_queryset(self):
        user = self.request.user
        application_id = self.request.query_params.get('application_id')

        if not application_id:
            return Application.objects.none()

        try:
            application = Application.objects.get(application_id=application_id)
        except Application.DoesNotExist:
            return Application.objects.none()

        if user.user_role == 'applicant' and application.applicant.user == user:
            if application.applicant_status == 'Deleted':
                return Application.objects.none()
            if application.applicant_status == 'Unread':
                application.applicant_status = 'Read'
                application.save(update_fields=['applicant_status'])
            return Application.objects.filter(application_id=application_id)

        if user.user_role == 'company' and application.internship_posting.company.user == user:
            if application.company_status == 'Deleted':
                return Application.objects.none()
            if application.company_status == 'Unread':
                application.company_status = 'Read'
                application.save(update_fields=['company_status'])
            return Application.objects.filter(application_id=application_id)

        return Application.objects.none()


@client_application_tag
class NotificationView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        user = self.request.user
        application = self.request.query_params.get('application')

        if user.user_role == 'applicant':
            return Notification.objects.filter(
                application=application,
                notification_type='Applicant'
            )

        elif user.user_role == 'company':
            return Notification.objects.filter(
                application=application,
                notification_type='Company'
            )

        else:
            return Notification.objects.none()


@client_application_tag
class ClearNotificationView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        user = request.user
        application_id = request.query_params.get('application_id')

        if not application_id:
            return Response({'error': 'Missing application_id in query parameters.'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            application = Application.objects.get(application_id=application_id)
        except Application.DoesNotExist:
            return Response({'error': 'Application not found.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if hasattr(user, 'applicant') and application.applicant == user.applicant:
            notifications = Notification.objects.filter(application=application)
        elif hasattr(user, 'company') and application.internship_posting.company == user.company:
            notifications = Notification.objects.filter(application=application)
        else:
            return Response({'error': 'You are not authorized to clear notifications for this application.'},
                            status=status.HTTP_403_FORBIDDEN)

        deleted_count, _ = notifications.delete()

        return Response({'message': f'{deleted_count} notifications cleared.'}, status=status.HTTP_200_OK)


@client_application_tag
class UpdateApplicationView(APIView):
    permission_classes = [IsAuthenticated, IsCompany]
    serializer_class = UpdateApplicationSerializer

    @transaction.atomic
    def put(self, request):
        application_id = request.query_params.get('application_id')

        try:
            application = Application.objects.get(application_id=application_id)
        except Application.DoesNotExist:
            return Response({'error': 'Application not found.'}, status=status.HTTP_400_BAD_REQUEST)

        if not application_id:
            return Response({'error': 'application_id query parameter is required.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if application.internship_posting.company.user != request.user:
            return Response({'error': 'You do not have permission to modify this application.'},
                            status=status.HTTP_403_FORBIDDEN)

        new_status = request.data.get('status')
        rejection_message = request.data.get('rejection_message', [])

        if new_status not in ['Onboarding', 'Rejected', 'Pending']:
            return Response({'error': 'Invalid status. You can only set status to'
                                      ' Pending, Onboarding, or Rejected.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if application.status == 'Dropped':
            return Response({'error': 'This application has been dropped. Cannot change status.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if application.status == 'Accepted':
            return Response({'error': 'This application has been accepted. Cannot change status.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if new_status == 'Rejected' and not rejection_message:
            return Response({'error': 'At least one rejection reason is required when rejecting an applicant.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if application.applicant_status != 'Deleted':
            application.applicant_status = 'Unread'
            application.save(update_fields=['applicant_status'])

        serializer = self.serializer_class(application, data={
            'status': new_status,
            'rejection_message': rejection_message
        }, partial=True)

        if serializer.is_valid():
            serializer.save()

            applicant = application.applicant
            applicant_email = applicant.user.email
            company_name = application.internship_posting.company.company_name
            internship_position = application.internship_posting.internship_position
            applicant_name = (
                    applicant.first_name +
                    (' ' + applicant.middle_initial if applicant.middle_initial else '') +
                    ' ' + applicant.last_name
            )

            if new_status == 'Rejected':
                subject = f"Your Internship Application Has Been Rejected"
                message_html = f"""
                            <div>
                                <p>Dear <strong>{applicant_name}</strong>,</p>
                                <p>Your application for the internship position 
                                   <strong>{internship_position}</strong> at <strong>{company_name}</strong> has been 
                                   <strong>rejected</strong>.</p>
                               <p><strong>Rejection Reasons:</strong></p>
                                <ul>
                                    {''.join(f'<li>{reason}</li>' for reason in rejection_message)}
                                </ul>
                                <p>We appreciate your interest and encourage you to explore other opportunities.</p>
                                <p>
                                    Best regards,<br>
                                    <strong>{company_name}</strong>
                                </p>
                            </div>
                            """
            else:
                subject = f"Your Internship Application Has Been Updated"
                message_html = f"""
                            <div>
                                <p>Dear <strong>{applicant_name}</strong>,</p>
                                <p>Your application for the position <strong>{internship_position}</strong> at 
                                <strong>{company_name}</strong> has been updated to <strong>{new_status}</strong>.</p>
                                <p>Thank you for your continued interest.</p>
                                <p>
                                    Best regards,<br>
                                    <strong>{company_name}</strong>
                                </p>
                            </div>
                            """

            # email = EmailMessage(
            #     subject=subject,
            #     body=message_html,
            #     from_email=formataddr((f'{company_name}', 'between_internships@gmail.com')),
            #     to=[applicant_email],
            #     reply_to=['no-reply@betweeninternships.com']
            # )
            # email.content_subtype = 'html'
            # email.send(fail_silently=False)

            Notification.objects.create(
                application=application,
                notification_text=f'Your application has been {new_status}.',
                notification_type='Applicant'
            )

            return Response({'message': f'Application has been set to {new_status}.'}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@client_application_tag
class RequestDocumentView(CreateAPIView):
    permission_classes = [IsAuthenticated, IsCompany]
    serializer_class = RequestDocumentSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            application = serializer.application
            company_user = application.internship_posting.company.user
            company_name = application.internship_posting.company.company_name

            if company_user != request.user:
                return Response(
                    {'error': 'You do not have permission to request documents for this application.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            try:
                serializer.send_request_email()

                Notification.objects.create(
                    application=application,
                    notification_text=f'{company_name} requested for documents.',
                    notification_type='Applicant'
                )

                if application.applicant_status != 'Deleted':
                    application.applicant_status = 'Unread'
                    application.save(update_fields=['applicant_status'])

                return Response({'message': 'Document request sent successfully.'}, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@client_application_tag
class DropApplicationView(APIView):
    permission_classes = [IsAuthenticated, IsApplicant]
    serializer_class = ApplicationSerializer

    @transaction.atomic
    def put(self, request):
        user = request.user
        application_id = request.query_params.get('application_id')

        try:
            application = Application.objects.get(application_id=application_id)
        except Application.DoesNotExist:
            return Response({'error': 'Application not found.'}, status=status.HTTP_400_BAD_REQUEST)

        if not application_id:
            return Response({'error': 'application_id query parameter is required.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if application.applicant.user != request.user:
            return Response({'error': 'You do not have permission to modify this application.'},
                            status=status.HTTP_403_FORBIDDEN)

        if application.status not in ['Pending', 'Onboarding']:
            return Response(
                {'error': 'You can only drop applications that are Pending or Onboarding.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        new_status = request.data.get('status')

        if new_status not in ['Dropped']:
            return Response({'error': 'Invalid status. You can only set status to'
                                      ' Dropped.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if application.company_status != 'Deleted':
            application.company_status = 'Unread'
            application.save(update_fields=['company_status'])

        serializer = self.serializer_class(application, data={'status': new_status}, partial=True)
        if serializer.is_valid():
            serializer.save()

            Endorsement.objects.filter(application=application).update(status='Deleted')

            Notification.objects.create(
                application=application,
                notification_text=f'The application has been dropped by the applicant.',
                notification_type='Company'
            )

            reset_recommendations_and_tap_count(user.applicant)
            run_internship_matching(user.applicant)

            return Response({'message': 'Application dropped successfully.'}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@client_application_tag
class AcceptApplicationView(APIView):
    permission_classes = [IsAuthenticated, IsApplicant]
    serializer_class = ApplicationSerializer

    @transaction.atomic
    def put(self, request):
        application_id = request.query_params.get('application_id')

        try:
            application = Application.objects.get(application_id=application_id)
        except Application.DoesNotExist:
            return Response({'error': 'Application not found.'}, status=status.HTTP_400_BAD_REQUEST)

        if not application_id:
            return Response({'error': 'application_id query parameter is required.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if application.applicant.user != request.user:
            return Response({'error': 'You do not have permission to modify this application.'},
                            status=status.HTTP_403_FORBIDDEN)

        if application.status not in ['Onboarding']:
            return Response(
                {'error': 'You can only accept applications that are Onboarding.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        new_status = request.data.get('status')

        if new_status not in ['Accepted']:
            return Response({'error': 'Invalid status. You can only set status to'
                                      ' Accepted.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if application.company_status != 'Deleted':
            application.company_status = 'Unread'
            application.save(update_fields=['company_status'])

        serializer = self.serializer_class(application, data={'status': new_status}, partial=True)
        if serializer.is_valid():
            serializer.save()

            internship_posting = application.internship_posting
            internship_posting.accepted_count = F('accepted_count') + 1
            internship_posting.save(update_fields=['accepted_count'])

            other_applications = Application.objects.filter(
                applicant=application.applicant
            ).exclude(
                Q(application_id=application_id) | Q(status='Deleted') | Q(status='Rejected')
            )

            other_applications.update(status='Dropped')

            for app in other_applications:
                Notification.objects.create(
                    application=app,
                    notification_text=f'The application has been Dropped by the Applicant.',
                    notification_type='Company'
                )

            Notification.objects.create(
                application=application,
                notification_text=f'The application has been Accepted by the applicant.',
                notification_type='Company'
            )

            company_email = application.internship_posting.company.user.email
            company_name = application.internship_posting.company.company_name
            applicant_name = f"{application.applicant.first_name} {application.applicant.last_name}"
            position = application.internship_posting.internship_position

            email_body = (
                f'Hello {company_name},<br><br>'
                f'The applicant <strong>{applicant_name}</strong> has accepted the application for '
                f'<strong>{position}</strong>.<br><br>'
                f'Please log in to your dashboard for more details.'
            )

            # email = EmailMessage(
            #     subject='An applicant has accepted your offer',
            #     body=email_body,
            #     from_email='Between_IMS <no-reply.between.internships@gmail.com>',
            #     to=[company_email],
            #     reply_to=['no-reply@betweeninternships.com']
            # )
            # email.content_subtype = 'html'
            # email.send(fail_silently=False)

            program = application.applicant.program
            ojt_coordinator =  OJTCoordinator.objects.get(program=program)
            coordinator_email = ojt_coordinator.user.email
            student_name = f"{application.applicant.first_name} {application.applicant.last_name}"

            if coordinator_email:
                subject = f"Internship Accepted by {student_name}"
                html_message = (
                    f"Dear {ojt_coordinator.first_name},<br><br>"
                    f"<strong>{student_name}</strong> has accepted an internship offer.<br><br>"
                    f"<strong>Program:</strong> {program.program_name}<br>"
                    f"<strong>Company:</strong> {company_name}<br>"
                    f"<strong>Internship Position:</strong> {position}<br><br>"
                    f"Please log in to see the accepted internship.<br><br>"
                    f"Best regards,<br><strong>Between IMS</strong>"
                )

                # email = EmailMessage(
                #     subject=subject,
                #     body=html_message,
                #     from_email='Between_IMS <no-reply.between.internships@gmail.com>',
                #     to=[coordinator_email],
                # )
                # email.content_subtype = "html"
                # email.send()

            return Response({'message': 'The Application has been accepted and the company was notified.'},
                            status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@client_application_tag
class RemoveFromBookmarksView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request):
        user = request.user
        application_id = request.query_params.get('application_id')

        if not application_id:
            return Response({'error': 'Missing application_id in query parameters.'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            application = Application.objects.get(application_id=application_id)
        except Application.DoesNotExist:
            return Response({'error': 'Application not found.'}, status=status.HTTP_404_NOT_FOUND)

        if application.status not in ['Dropped', 'Rejected']:
            return Response({'error': 'Only applications with status "Dropped" and "Rejected"'
                                      ' can be removed from bookmarks.'},
                            status=status.HTTP_403_FORBIDDEN)

        if user.user_role == 'applicant' and application.applicant.user == user:
            application.applicant_status = 'Deleted'
            application.save(update_fields=['applicant_status'])

            InternshipRecommendation.objects.filter(
                applicant=application.applicant,
                internship_posting=application.internship_posting
            ).update(
                status='Skipped',
                time_stamp=timezone.now()
            )

            reset_recommendations_and_tap_count(user.applicant)
            run_internship_matching(user.applicant)

            return Response({'message': 'Application removed from bookmarks (applicant).'}, status=status.HTTP_200_OK)

        if user.user_role == 'company' and application.internship_posting.company.user == user:
            application.company_status = 'Deleted'
            application.save(update_fields=['company_status'])
            return Response({'message': 'Application removed from bookmarks (company).'}, status=status.HTTP_200_OK)

        return Response({'error': 'You are not authorized to modify this application.'},
                        status=status.HTTP_403_FORBIDDEN)


@client_application_tag
class SendDocumentView(APIView):
    permission_classes = [IsAuthenticated, IsApplicant]

    @transaction.atomic
    def post(self, request):
        serializer = SendDocumentSerializer(data=request.data)

        if serializer.is_valid():
            application = serializer.application

            files = request.FILES.getlist('files')
            if not files:
                return Response({'error': 'At least one file is required.'}, status=status.HTTP_400_BAD_REQUEST)

            for f in files:
                if f.size > 5 * 1024 * 1024:
                    return Response(
                        {'error': f"The file '{f.name}' exceeds the 5MB size limit."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                serializer.send_document_email(files)

                Notification.objects.create(
                    application=application,
                    notification_text=f'The applicant has sent additional documents.',
                    notification_type='Company'
                )

                if application.company_status != 'Deleted':
                    application.company_status = 'Unread'
                    application.save(update_fields=['company_status'])

                return Response({'message': 'Documents sent successfully.'}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@client_application_tag
class NewNotificationsView(APIView):
    permission_classes = [IsAuthenticated, IsCompany]

    def get(self, request, *args, **kwargs):
        user = request.user

        unread_count = Application.objects.filter(
            internship_posting__company__user=user,
            company_status='Unread'
        ).count()

        return Response({'new_notifications': unread_count})


class DroppedApplicationsView(APIView):
    permission_classes = [IsAuthenticated, IsCompany]

    def get(self, request, *args, **kwargs):
        user = request.user

        dropped_applications = Application.objects.filter(
            internship_posting__company__user=user,
            status='Dropped'
        ).count()

        return Response({'dropped_applications': dropped_applications})


class UninterestedView(APIView):
    permission_classes = [IsAuthenticated, IsCompany]

    def get(self, request, *args, **kwargs):
        user = request.user

        uninterested = InternshipRecommendation.objects.filter(
            internship_posting__company__user=user,
            status='Skipped'
        ).count()

        return Response({'uninterested': uninterested})


