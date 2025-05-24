from django.shortcuts import render
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from client_application.models import Application
from client_application.serializers import ApplicationListSerializer


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

