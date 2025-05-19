from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from client_matching.admin import InternshipRecommendationInline
from .forms import DateJoinedFilter
from .models import (User, Applicant, Company, CareerEmplacementAdmin, OJTCoordinator)


model_to_register = [CareerEmplacementAdmin, OJTCoordinator]

for model in model_to_register:
    admin.site.register(model)


# For making Users model view only
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User

    list_display = ('user_id', 'status', 'user_role', 'is_staff', 'date_joined')

    ordering = ('status',)

    list_filter = ('status', 'user_role', 'is_staff', 'date_joined')

    readonly_fields = (
        'email', 'user_id', 'date_joined', 'date_modified',
        'status', 'user_role', 'is_staff', 'is_superuser',
        'groups', 'user_permissions'
    )

    fieldsets = (
        (None, {'fields': ('email', 'user_id', 'status', 'user_role')}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('date_joined', 'date_modified', 'verified_at',)}),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True


# For displaying selected skills of applicant
@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):
    list_display = ('get_email', 'preferred_modality', 'in_practicum', 'get_date_joined')
    inlines = [InternshipRecommendationInline]

    list_filter = ('preferred_modality', 'in_practicum', DateJoinedFilter)

    exclude = ('hard_skills', 'soft_skills')

    fieldsets = (
        (None, {
            'fields': (
                'user', 'first_name', 'last_name', 'middle_initial',
                'school', 'department', 'program',
                'academic_program', 'address', 'preferred_modality',
                'quick_introduction', 'in_practicum'
            )
        }),
        ('Skills', {
            'fields': ('display_hard_skills', 'display_soft_skills'),
        }),
        ('Documents', {
            'fields': ('resume', 'enrollment_record'),
        }),
        ('Internship Matching', {
            'fields': ('last_matched', 'tap_count', 'last_recommendation_filter_state'),
        }),
    )

    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'email'

    def get_date_joined(self, obj):
        return obj.user.date_joined
    get_date_joined.short_description = 'date_joined'

    def display_hard_skills(self, obj):
        skills = "<br>".join([skill.name for skill in obj.hard_skills.all()])
        return mark_safe(skills)
    display_hard_skills.short_description = "Selected Hard Skills"

    def display_soft_skills(self, obj):
        skills = "<br>".join([skill.name for skill in obj.soft_skills.all()])
        return mark_safe(skills)
    display_soft_skills.short_description = "Selected Soft Skills"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        'company_name',
        'business_nature',
        'company_website_url',
    )

    list_filter = ('business_nature',)

    fieldsets = (
        (None, {
            'fields': (
                'company_id', 'user', 'get_email', 'company_name', 'company_address',
                'company_information', 'business_nature',
            )
        }),
        ('Web & Social Links', {
            'fields': (
                'company_website_url', 'linkedin_url', 'facebook_url',
                'instagram_url', 'x_url', 'other_url',
            )
        }),
        ('Image urls', {
            'fields': (
                'background_image', 'profile_picture',
            )
        })
    )

    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True

