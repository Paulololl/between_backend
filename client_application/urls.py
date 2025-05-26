from django.urls import path

from client_application.views import ApplicationListView, ApplicationDetailView

urlpatterns = [
    path('get/applications/', ApplicationListView.as_view()),
    path('get/application_detail/', ApplicationDetailView.as_view()),
]