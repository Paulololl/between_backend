from django.shortcuts import render
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from client_application.models import Application
from client_application.serializers import ApplicationListSerializer, ApplicationDetailSerializer


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


