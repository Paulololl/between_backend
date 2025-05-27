from django.urls import path

from client_application.views import ApplicationListView, ApplicationDetailView, NotificationView, \
    UpdateApplicationView

urlpatterns = [
    path('get/applications/', ApplicationListView.as_view()),
    path('get/application_detail/', ApplicationDetailView.as_view()),
    path('notifications/', NotificationView.as_view()),
    path('update/application/', UpdateApplicationView.as_view()),
]
