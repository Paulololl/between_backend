from django.urls import path
from . import views

urlpatterns = [
    path('partnered-companies/', views.SchoolPartnershipListView.as_view(), name="partnered-companies"),
    path('students/', views.ApplicantListView.as_view(), name='student-list'),
    path('endorsements/', views.EndorsementListView.as_view(), name='endorsement-list'),
    path('responded_endorsements/', views.RespondedEndorsementListView.as_view()),
]