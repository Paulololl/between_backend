from django.urls import path

from client_matching.views import PersonInChargeListView, CreatePersonInChargeView, EditPersonInChargeView, \
    BulkDeletePersonInChargeView

urlpatterns = [
    path('person_in_charge/', PersonInChargeListView.as_view()),
    path('create/person_in_charge/', CreatePersonInChargeView.as_view()),
    path('edit/person_in_charge/', EditPersonInChargeView.as_view()),
    path('bulk-delete/person_in_charge/', BulkDeletePersonInChargeView.as_view()),
]