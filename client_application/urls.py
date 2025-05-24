from django.urls import path

from client_application.views import ApplicationListView


urlpatterns = [
    path('get/applications/', ApplicationListView.as_view()),
]