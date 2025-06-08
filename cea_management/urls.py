from django.urls import path
from . import views

urlpatterns = [
    path('ojt-coordinators/', views.OJTCoordinatorListView.as_view(), name="ojt-coordinators-list"),
    path('ojt-coordinators/create/', views.CreateOJTCoordinatorView.as_view(), name="ojt-coordinators-create"),
    path('ojt-coordinators/update/', views.UpdateOJTCoordinatorView.as_view(), name="ojt-coordinators-update"),
    path('ojt-coordinators/remove/', views.RemoveOJTCoordinatorView.as_view(), name="ojt-coordinators-remove"),
    path('partnerships/', views.SchoolPartnershipListView.as_view(), name="partnerships-list"),
    path('partnerships/create/', views.CreateSchoolPartnershipView.as_view(), name="partnerships-create"),
    path('partnerships/delete/', views.BulkDeleteSchoolPartnershipView.as_view(), name="partnerships-delete"),
    path('students/', views.ApplicantListView.as_view(), name="students-list"),
    path('companies/', views.CompanyListView.as_view(), name="companies-list"),
    path('cea/', views.CareerEmplacementAdminView.as_view(), name="get-cea"),
]