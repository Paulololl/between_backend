from django.urls import path
from . import views

urlpatterns = [
    path('partnered-companies/', views.PartneredCompaniesListView.as_view(), name="partnerships-companies"),
]