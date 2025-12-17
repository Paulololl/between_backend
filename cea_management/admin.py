from django.contrib import admin

from .forms import CustomProgramForm, SchoolFilter
from .models import (SchoolPartnershipList, Department, Program, School)


model_to_register = [SchoolPartnershipList, School]

for model in model_to_register:
    admin.site.register(model)


@admin.register(Department)
class CustomDepartment(admin.ModelAdmin):
    model = Department

    list_display = ('department_name', 'school')

    list_filter = ('school',)

    fieldsets = (
        (None, {'fields': ('school', 'department_name')}),
    )


@admin.register(Program)
class CustomProgram(admin.ModelAdmin):
    model = Program
    form = CustomProgramForm

    list_display = ('program_name', 'department', 'school_name')

    list_filter = ('department', SchoolFilter)

    fieldsets = (
        (None, {'fields': ('department', 'program_name',)}),
    )

    def school_name(self, obj):
        return obj.department.school.school_name
