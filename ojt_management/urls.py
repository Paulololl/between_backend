from django.urls import path
from . import views

urlpatterns = [
    path('partnered-companies/', views.SchoolPartnershipListView.as_view(), name="partnerships-companies"),
    path('students/', views.StudentListView.as_view(), name='student-list'),
]