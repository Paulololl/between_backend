from django.urls import path

from client_matching.views import PersonInChargeListView, CreatePersonInChargeView, EditPersonInChargeView, \
    BulkDeletePersonInChargeView, InternshipPostingListView, CreateInternshipPostingView, EditInternshipPostingView, \
    BulkDeleteInternshipPostingView, ToggleInternshipPostingView

urlpatterns = [
    path('internship_posting/', InternshipPostingListView.as_view()),
    path('create/internship_posting/', CreateInternshipPostingView.as_view()),
    path('edit/internship_posting/', EditInternshipPostingView.as_view()),
    path('bulk-delete/internship_posting/', BulkDeleteInternshipPostingView.as_view()),
    path('toggle/internship_posting/', ToggleInternshipPostingView.as_view()),
    path('person_in_charge/', PersonInChargeListView.as_view()),
    path('create/person_in_charge/', CreatePersonInChargeView.as_view()),
    path('edit/person_in_charge/', EditPersonInChargeView.as_view()),
    path('bulk-delete/person_in_charge/', BulkDeletePersonInChargeView.as_view()),
]