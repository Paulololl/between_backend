from django.urls import path

from client_application.views import ApplicationListView, ApplicationDetailView, NotificationView, \
    UpdateApplicationView, RequestDocumentView, ClearNotificationView

urlpatterns = [
    path('get/applications/', ApplicationListView.as_view()),
    path('get/application_detail/', ApplicationDetailView.as_view()),
    path('notifications/', NotificationView.as_view()),
    path('clear_notifications/', ClearNotificationView.as_view()),
    path('update/application/', UpdateApplicationView.as_view()),
    path('application/request_document/', RequestDocumentView.as_view()),
]
