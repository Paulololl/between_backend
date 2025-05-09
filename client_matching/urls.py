from django.urls import path

from client_matching.views import PersonInChargeListView, CreatePersonInChargeView, EditPersonInChargeView, \
    DeletePersonInChargeView

urlpatterns = [
    path('person_in_charge/', PersonInChargeListView.as_view()),
    path('create/person_in_charge/', CreatePersonInChargeView.as_view()),
    path('edit/person_in_charge/<uuid:pk>/', EditPersonInChargeView.as_view()),
    path('delete/person_in_charge/<uuid:pk>/', DeletePersonInChargeView.as_view()),
]