from django.urls import path
from . import views

urlpatterns = [
    path('partnered-companies/', views.SchoolPartnershipListView.as_view(), name="partnered-companies"),
    path('students/', views.ApplicantListView.as_view(), name='student-list'),
    path('students/in_practicum/', views.GetPracticumStudentListView.as_view(), name='students-in-practicum'),
    path('students/in_practicum/end/', views.EndPracticumView.as_view(), name='student-in-practicum-end'),
]