from django import forms
from .models import Program, School


class CustomProgramForm(forms.ModelForm):
    department = forms.ChoiceField(choices=[])

    class Meta:
        model = Program
        fields = ['program_name', 'department']

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
