from django.urls import path
from . import views

urlpatterns = [
    path('partnered-companies/', views.SchoolPartnershipListView.as_view(), name="partnered-companies"),
    path('students/', views.ApplicantListView.as_view(), name='student-list'),
    path('students/reqeusting_practicum/', views.GetRequestPracticumListView.as_view(), name='students-requesting-practicum'),
    path('students/in_practicum/', views.GetPracticumStudentListView.as_view(), name='students-in-practicum'),
    path('students/in_practicum/end/', views.EndPracticumView.as_view(), name='student-in-practicum-end'),
    path('students/in_practicum/approve/', views.ApprovePracticumRequestView.as_view(), name='student-in-practicum-approve'),
    path('students/in_practicum/reject/', views.RejectPracticumRequestView.as_view(), name='student-in-practicum-reject'),
    path('')
]