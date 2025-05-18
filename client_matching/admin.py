from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import (HardSkillsTagList, SoftSkillsTagList, InternshipPosting, InternshipRecommendation,
                     Report, MinQualification, Benefit, Advertisement, KeyTask, PersonInCharge)


model_to_register = [Report, MinQualification, Benefit, Advertisement, KeyTask, PersonInCharge]

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


@admin.register(InternshipPosting)
class CustomInternshipPosting(admin.ModelAdmin):
    model = InternshipPosting

    list_display = ('internship_posting_id', 'internship_position', 'status', 'display_company_name',
                    'person_in_charge')

    list_filter = ('company', 'status')

    readonly_fields = (
        'internship_posting_id',
        'company',
        'display_hard_skills',
        'display_soft_skills',
        'display_key_tasks',
        'display_min_qualifications',
        'display_benefits',
    )

    fieldsets = (
        (None, {
            'fields': ('internship_posting_id', 'company', 'person_in_charge', 'internship_position',
                       'address', 'other_requirements', 'is_paid_internship', 'is_only_for_practicum', 'status',
                       'internship_date_start', 'application_deadline', 'date_created', 'date_modified'),
        }),
        ('Benefits', {
            'fields': ('display_benefits',),
        }),
        ('Key Tasks', {
            'fields': ('display_key_tasks',),
        }),
        ('Min Qualifications', {
            'fields': ('display_min_qualifications',),
        }),
        ('Skills', {
            'fields': ('display_hard_skills', 'display_soft_skills'),
        }),
    )

    def display_hard_skills(self, obj):
        skills = "<br>".join([skill.name for skill in obj.required_hard_skills.all()])
        return mark_safe(skills)

    display_hard_skills.short_description = "Hard Skills"

    def display_soft_skills(self, obj):
        skills = "<br>".join([skill.name for skill in obj.required_soft_skills.all()])
        return mark_safe(skills)

    display_soft_skills.short_description = "Soft Skills"

    def display_key_tasks(self, obj):
        tasks = "<br>".join([task.key_task for task in obj.key_tasks.all()])
        return mark_safe(tasks)

    display_key_tasks.short_description = "Key Tasks"

    def display_min_qualifications(self, obj):
        qualifications = "<br>".join([qual.min_qualification for qual in obj.min_qualifications.all()])
        return mark_safe(qualifications)

    display_min_qualifications.short_description = "Min Qualifications"

    def display_benefits(self, obj):
        benefits = "<br>".join([b.benefit for b in obj.benefits.all()])
        return mark_safe(benefits)

    display_benefits.short_description = "Benefits"

    def display_company_name(self, obj):
        return obj.company.company_name if obj.company else "-"

    display_company_name.short_description = "Company Name"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True


@admin.register(InternshipRecommendation)
class InternshipRecommendationAdmin(admin.ModelAdmin):
    list_display = ('recommendation_id', 'applicant_email', 'similarity_score', 'status')
    list_filter = ('status',)
    search_fields = ('applicant__user__email',)

    def applicant_email(self, obj):
        return obj.applicant.user.email
    applicant_email.admin_order_field = 'applicant__user__email'
    applicant_email.short_description = 'Applicant Email'


class InternshipRecommendationInline(admin.TabularInline):
    model = InternshipRecommendation
    extra = 0
    readonly_fields = ('internship_posting', 'similarity_score', 'status', 'time_stamp')
    can_delete = False


