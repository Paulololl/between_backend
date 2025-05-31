from django.shortcuts import render
from rest_framework import serializers, status
from rest_framework.generics import ListAPIView, CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from client_application.models import Application, Notification
from client_application.serializers import ApplicationListSerializer, ApplicationDetailSerializer, \
    NotificationSerializer, UpdateApplicationSerializer, RequestDocumentSerializer, DropApplicationSerializer
from user_account.permissions import IsCompany, IsApplicant


class ApplicationListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ApplicationListSerializer

    def get_queryset(self):
        user = self.request.user

        if user.user_role == 'applicant':
            queryset = Application.objects.filter(applicant__user=user).exclude(applicant_status='Deleted')
        elif user.user_role == 'company':
            queryset = Application.objects.filter(internship_posting__company__user=user).exclude(company_status='Deleted')
        else:
            return Application.objects.none()

        application_status = self.request.query_params.get('application_status')
        allowed_status = ['Confirmed', 'Pending', 'Rejected', 'Dropped']
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
        if user.user_role == 'company' and internship_position:
            queryset = queryset.filter(
                internship_posting__internship_position__iexact=internship_position
            )

        return queryset


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


class UpdateApplicationView(APIView):
    permission_classes = [IsAuthenticated, IsCompany]
    serializer_class = UpdateApplicationSerializer

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

        if new_status not in ['Confirmed', 'Rejected', 'Pending']:
            return Response({'error': 'Invalid status. You can only set status to'
                                      ' Pending, Confirmed, or Rejected.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if application.status == 'Dropped':
            return Response({'error': 'This application has been dropped. Cannot change status.'},
                            status=status.HTTP_400_BAD_REQUEST)

        application.applicant_status = 'Unread'
        application.save(update_fields=['applicant_status'])

        serializer = self.serializer_class(application, data={'status': new_status}, partial=True)
        if serializer.is_valid():
            serializer.save()

            Notification.objects.create(
                application=application,
                notification_text=f'Your application has been set to {new_status}.',
                notification_type='Applicant'
            )

            return Response({'message': f'Application has been set to {new_status}.'}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RequestDocumentView(CreateAPIView):
    permission_classes = [IsAuthenticated, IsCompany]
    serializer_class = RequestDocumentSerializer

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
                    notification_text=f'You have a new email from {company_name}.',
                    notification_type='Applicant'
                )

                application.applicant_status = 'Unread'
                application.save(update_fields=['applicant_status'])

                return Response({'message': 'Document request sent successfully.'}, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DropApplicationView(APIView):
    permission_classes = [IsAuthenticated, IsApplicant]
    serializer_class = DropApplicationSerializer

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

        new_status = request.data.get('status')

        if new_status not in ['Dropped']:
            return Response({'error': 'Invalid status. You can only set status to'
                                      ' Dropped.'},
                            status=status.HTTP_400_BAD_REQUEST)

        application.company_status = 'Unread'
        application.save(update_fields=['company_status'])

        serializer = self.serializer_class(application, data={'status': new_status}, partial=True)
        if serializer.is_valid():
            serializer.save()

            Notification.objects.create(
                application=application,
                notification_text=f'The application has been dropped by the applicant.',
                notification_type='Company'
            )

            return Response({'message': 'Application dropped successfully.'}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RemoveFromBookmarksView(APIView):
    permission_classes = [IsAuthenticated]

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
            return Response({'message': 'Application removed from bookmarks (applicant).'}, status=status.HTTP_200_OK)

        if user.user_role == 'company' and application.internship_posting.company.user == user:
            application.company_status = 'Deleted'
            application.save(update_fields=['company_status'])
            return Response({'message': 'Application removed from bookmarks (company).'}, status=status.HTTP_200_OK)

        return Response({'error': 'You are not authorized to modify this application.'},
                        status=status.HTTP_403_FORBIDDEN)
