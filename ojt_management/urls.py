from django.urls import path
from . import views
from .views import EndorsementDetailView, RequestEndorsementView, UpdateEndorsementView, GenerateEndorsementPDFView, \
    ChangeLogoAndSignatureView, CoordinatorAuditLogView, PartneredCompaniesMetricsView, \
    TotalSearchingForPracticumMetricsView, EndorsementRequestMetricView

urlpatterns = [
    path('partnered-companies/', views.SchoolPartnershipListView.as_view()),
    path('students/', views.ApplicantListView.as_view()),
    path('responded_endorsements/', views.RespondedEndorsementListView.as_view()),
    path('endorsement_detail/', EndorsementDetailView.as_view()),
    path('request_endorsement/', RequestEndorsementView.as_view()),
    path('update_endorsement/', UpdateEndorsementView.as_view()),
    path('generate_endorsement_letter/', GenerateEndorsementPDFView.as_view()),
    path('students/reqeusting_practicum/', views.GetRequestPracticumListView.as_view()),
    path('students/requesting_practicum/enrollment_record/', views.GetEnrollmentRecordView.as_view()),
    path('students/requesting_practicum/approve/', views.ApprovePracticumRequestView.as_view()),
    path('students/requesting_practicum/reject/', views.RejectPracticumRequestView.as_view()),
    path('students/in_practicum/', views.GetPracticumStudentListView.as_view()),
    path('students/in_practicum/end/', views.EndPracticumView.as_view()),
    path('students/in_practicum/reset/', views.ResetPracticumView.as_view()),
    path('ojtcoordinator/edit-logo-signature/', ChangeLogoAndSignatureView.as_view()),
    path('ojtcoordinator/audit_logs/', CoordinatorAuditLogView.as_view()),
    path('metrics/partnered_companies/', PartneredCompaniesMetricsView.as_view()),
    path('metrics/total_searching_for_practicum/', TotalSearchingForPracticumMetricsView.as_view()),
    path('metrics/endorsement_requests/', EndorsementRequestMetricView.as_view()),
]