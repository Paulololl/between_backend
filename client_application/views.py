from django.shortcuts import render
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from client_application.models import Application, Notification
from client_application.serializers import ApplicationListSerializer, ApplicationDetailSerializer, \
    NotificationSerializer, SortApplicationSerializer


class ApplicationListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ApplicationListSerializer

    def get_queryset(self):
        user = self.request.user

        if user.user_role == 'applicant':
            return Application.objects.filter(applicant__user=user)

        elif user.user_role == 'company':
            return Application.objects.filter(internship_posting__company__user=user)

        else:
            return Application.objects.none()


class ApplicationDetailView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ApplicationDetailSerializer

    def get_queryset(self):
        user = self.request.user
        application_id = self.request.query_params.get('application_id')

        if user.user_role == 'applicant':
            return Application.objects.filter(
                applicant__user=user,
                application_id=application_id
            )

        elif user.user_role == 'company':
            return Application.objects.filter(
                internship_posting__company__user=user,
                application_id=application_id
            )

        else:
            return Application.objects.none()


class NotificationView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        user = self.request.user
        # application_id = self.request.query_params.get('application_id')

        if user.user_role == 'applicant':
            return Notification.objects.filter(
                # application_id=application_id,
                notification_type='Applicant'
            )

        elif user.user_role == 'company':
            return Notification.objects.filter(
                # application_id=application_id,
                notification_type='Company'
            )

        else:
            return Notification.objects.none()


class SortApplicationView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SortApplicationSerializer

    def get_queryset(self):
        user = self.request.user

        if user.user_role == 'applicant':
            queryset = Application.objects.filter(applicant__user=user)
        elif user.user_role == 'company':
            queryset = Application.objects.filter(internship_posting__company__user=user)
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
                    queryset = queryset.filter(is_viewed_applicant=True)
                elif user.user_role == 'company':
                    queryset = queryset.filter(is_viewed_company=True)
            elif view_status == 'Unread':
                if user.user_role == 'applicant':
                    queryset = queryset.filter(is_viewed_applicant=False)
                elif user.user_role == 'company':
                    queryset = queryset.filter(is_viewed_company=False)

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



