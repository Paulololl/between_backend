from django.contrib import admin

from .models import (HardSkillsTagList, SoftSkillsTagList, InternshipPosting, InternshipRecommendation,
                     Report, MinQualification, Benefit, Advertisement, KeyTask, PersonInCharge)


model_to_register = [InternshipPosting, InternshipRecommendation,
                     Report, MinQualification, Benefit, Advertisement, KeyTask, PersonInCharge]

for model in model_to_register:
    admin.site.register(model)


@admin.register(HardSkillsTagList)
class CustomDepartment(admin.ModelAdmin):
    model = HardSkillsTagList

    list_display = ('name',)

    # list_filter = ('school',)

    fieldsets = (
        (None, {'fields': ('lightcast_identifier', 'name')}),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True


@admin.register(SoftSkillsTagList)
class CustomDepartment(admin.ModelAdmin):
    model = HardSkillsTagList

    list_display = ('name',)

    # list_filter = ('school',)

    fieldsets = (
        (None, {'fields': ('lightcast_identifier', 'name')}),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True
