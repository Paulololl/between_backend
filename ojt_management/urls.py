from django.urls import path
from . import views
from .views import EndorsementDetailView, RequestEndorsementView, UpdateEndorsementView

urlpatterns = [
    path('partnered-companies/', views.SchoolPartnershipListView.as_view(), name="partnered-companies"),
    path('students/', views.ApplicantListView.as_view(), name='student-list'),
    path('endorsements/', views.EndorsementListView.as_view(), name='endorsement-list'),
    path('responded_endorsements/', views.RespondedEndorsementListView.as_view()),
    path('endorsement_detail/', EndorsementDetailView.as_view()),
    path('request_endorsement/', RequestEndorsementView.as_view()),
    path('update_endorsement/', UpdateEndorsementView.as_view()),
]