from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import (HardSkillsTagList, SoftSkillsTagList, InternshipPosting, InternshipRecommendation,
                     Report, MinQualification, Benefit, Advertisement, KeyTask, PersonInCharge)
from .utils import InternshipPostingStatusFilter

model_to_register = [MinQualification, Benefit, Advertisement, KeyTask, PersonInCharge]

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

    def get_model_perms(self, request):
        if not request.user.is_superuser:
            return {}
        return super().get_model_perms(request)

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

    def get_model_perms(self, request):
        if not request.user.is_superuser:
            return {}
        return super().get_model_perms(request)

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
        'modality'
    )

    fieldsets = (
        (None, {
            'fields': ('internship_posting_id', 'company', 'person_in_charge', 'internship_position', 'modality',
                       'address', 'other_requirements', 'is_paid_internship', 'is_only_for_practicum', 'status',
                       'ojt_hours', 'internship_date_start', 'application_deadline', 'date_created', 'date_modified',
                       'latitude', 'longitude')
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

    def get_model_perms(self, request):
        if not request.user.is_superuser:
            return {}
        return super().get_model_perms(request)

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
    list_display = (
                    'internship_position',
                    'recommendation_id',
                    'applicant_email',
                    'similarity_score',
                    'status',
                    'posting_status'
                   )
    list_filter = ('status', InternshipPostingStatusFilter)
    search_fields = ('applicant__user__email', 'internship_posting__internship_position')

    def internship_position(self, obj):
        return obj.internship_posting.internship_position
    internship_position.short_description = "Internship Posting"

    def applicant_email(self, obj):
        return obj.applicant.user.email
    applicant_email.admin_order_field = 'applicant__user__email'
    applicant_email.short_description = 'Applicant Email'

    def posting_status(self, obj):
        if obj.internship_posting:
            return obj.internship_posting.status
        return 'Deleted or Missing'
    posting_status.short_description = 'Internship Posting'

    def get_model_perms(self, request):
        if not request.user.is_superuser:
            return {}
        return super().get_model_perms(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    model = Report

    list_display = ('report_id', 'display_position', 'display_company_name', 'status')

    list_filter = ('status',)

    readonly_fields = ('description', 'internship_posting')

    fieldsets = (
        (None, {
            'fields': ('internship_posting', 'description', 'status')
        }),
    )

    def display_position(self, obj):
        return obj.internship_posting.internship_position if obj.internship_posting else '-'
    display_position.short_description = 'Internship Posting'

    def display_company_name(self, obj):
        return obj.internship_posting.company.company_name\
            if (obj.internship_posting and obj.internship_posting.company) else "-"
    display_company_name.short_description = "Company"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return True


class InternshipRecommendationInline(admin.TabularInline):
    model = InternshipRecommendation
    extra = 0
    readonly_fields = ('internship_posting', 'modality', 'similarity_score', 'status', 'posting_status', 'time_stamp')
    can_delete = False

    def posting_status(self, obj):
        try:
            posting = InternshipPosting.objects.get(internship_posting_id=obj.internship_posting_id)
            return posting.status
        except InternshipPosting.DoesNotExist:
            return 'Deleted or Missing'
    posting_status.short_description = 'Posting Status'

    def modality(self, obj):
        try:
            return obj.internship_posting.modality
        except InternshipPosting.DoesNotExist:
            return 'N/A'

    modality.short_description = 'Modality'

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True


