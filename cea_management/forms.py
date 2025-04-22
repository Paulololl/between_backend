from django import forms
from django.contrib import admin

from .models import School, Department


class CustomProgramForm(forms.ModelForm):
    department = forms.ModelChoiceField(queryset=Department.objects.all())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        grouped_choices = []
        schools = School.objects.prefetch_related('departments').order_by('school_name')

        for school in schools:
            departments = school.departments.all().order_by('department_name')
            if departments:
                department_choices = [(dept.department_id, dept.department_name) for dept in departments]
                grouped_choices.append((school.school_name, department_choices))

        self.fields['department'].choices = grouped_choices


class SchoolFilter(admin.SimpleListFilter):
    title = 'school'
    parameter_name = 'school'

    def lookups(self, request, model_admin):
        schools = School.objects.all().order_by('school_name')
        return [(str(school.pk), school.school_name) for school in schools]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(department__school__pk=self.value())
        return queryset
    