from django.urls import path

from .views import ApplicantRegisterView, NestedSchoolDepartmentProgramListView, DepartmentListView, ProgramListView, \
    SchoolListView, CompanyRegisterView, CareerEmplacementAdminRegisterView, OJTCoordinatorRegisterView, \
    MyTokenObtainPairView, EmailLoginView, SchoolEmailCheckView, GetApplicantView, MyTokenRefreshView, VerifyEmailView, \
    GetCompanyView, ForgotPasswordLinkView, ResetPasswordView, DeleteAccountView, ChangePasswordView, \
    GetOJTCoordinatorView, EditCompanyView, EditApplicantView, GetUserView, GetEmailView

urlpatterns = [
    path('user/', GetUserView.as_view()),
    path('email/', GetEmailView.as_view()),
    path('applicant/', GetApplicantView.as_view()),
    path('company/', GetCompanyView.as_view()),
    path('edit-company/', EditCompanyView.as_view()),
    path('edit-applicant/', EditApplicantView.as_view()),
    path('ojtcoordinator/', GetOJTCoordinatorView.as_view()),
    path('forgot-password/', ForgotPasswordLinkView.as_view()),
    path('forgot-password/<uidb64>/<token>/', ForgotPasswordLinkView.as_view()),
    path('reset-password/', ResetPasswordView.as_view()),
    path('register/applicant/', ApplicantRegisterView.as_view()),
    path('register/applicant/school_verify/', SchoolEmailCheckView.as_view()),
    path('register/company/', CompanyRegisterView.as_view()),
    path('register/cea/', CareerEmplacementAdminRegisterView.as_view()),
    path('register/ojt_coordinator/', OJTCoordinatorRegisterView.as_view()),
    path('schools/', SchoolListView.as_view()),
    path('departments/', DepartmentListView.as_view()),
    path('programs/', ProgramListView.as_view()),
    path('schools/departments/programs/', NestedSchoolDepartmentProgramListView.as_view()),
    path('login/token/', MyTokenObtainPairView.as_view()),
    path('token/refresh/', MyTokenRefreshView.as_view()),
    path('login/email/', EmailLoginView.as_view()),
    path('verify-email/', VerifyEmailView.as_view()),
    path('verify-email/<uidb64>/<token>/', VerifyEmailView.as_view()),
    path('delete-account/', DeleteAccountView.as_view()),
    path('change-password/', ChangePasswordView.as_view()),


]