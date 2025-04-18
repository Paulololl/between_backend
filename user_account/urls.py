from django.urls import path
from .views import ApplicantRegisterView, SchoolListView, DepartmentListView, ProgramListView

urlpatterns = [
    path('register/applicant/', ApplicantRegisterView.as_view()),
    path('schools/', SchoolListView.as_view()),
    path('departments/', DepartmentListView.as_view()),
    path('programs/', ProgramListView.as_view())
]