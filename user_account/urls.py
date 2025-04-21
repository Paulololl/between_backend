from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import ApplicantRegisterView, NestedSchoolDepartmentProgramListView, DepartmentListView, ProgramListView, \
    SchoolListView, CompanyRegisterView, CareerEmplacementAdminRegisterView, OJTCoordinatorRegisterView, \
    MyTokenObtainPairView, EmailLoginView

urlpatterns = [
    path('register/applicant/', ApplicantRegisterView.as_view()),
    path('register/company/', CompanyRegisterView.as_view()),
    path('register/cea/', CareerEmplacementAdminRegisterView.as_view()),
    path('register/ojt_coordinator/', OJTCoordinatorRegisterView.as_view()),
    path('schools/', SchoolListView.as_view()),
    path('departments/', DepartmentListView.as_view()),
    path('programs/', ProgramListView.as_view()),
    path('schools/departments/programs/', NestedSchoolDepartmentProgramListView.as_view()),
    path('login/token/', MyTokenObtainPairView.as_view()),
    path('token/refresh/', TokenRefreshView.as_view()),
    path('login/email/', EmailLoginView.as_view())

]