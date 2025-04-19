from django.urls import path
from .views import ApplicantRegisterView, NestedSchoolDepartmentProgramListView, DepartmentListView, ProgramListView, \
    SchoolListView

urlpatterns = [
    path('register/applicant/', ApplicantRegisterView.as_view()),
    path('schools/', SchoolListView.as_view()),
    path('departments/', DepartmentListView.as_view()),
    path('programs/', ProgramListView.as_view()),
    path('schools/departments/programs/', NestedSchoolDepartmentProgramListView.as_view()),
]