from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password, password_validators_help_text_html
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from client_matching.admin import InternshipRecommendationInline
from .forms import DateJoinedFilter
from .models import (User, Applicant, Company, CareerEmplacementAdmin, OJTCoordinator, AuditLog)


model_to_register = [CareerEmplacementAdmin, OJTCoordinator]

for model in model_to_register:
    admin.site.register(model)


class UserAdminForm(UserCreationForm):
    class Meta:
        model = User
        fields = '__all__'

    readonly_fields = (
        'user_id', 'date_joined', 'date_modified', 'verified_at'  # 'email'
        'is_superuser',  # 'is_staff', 'user_role'
        'user_permissions'  # 'groups'
    )

    def clean(self):
        cleaned_data = super().clean()
        user_role = cleaned_data.get('user_role')
        groups = cleaned_data.get('groups') or []
        is_staff = cleaned_data.get('is_staff')

        system_admin_group = Group.objects.filter(name='System Admin').first()

        if system_admin_group and system_admin_group in groups:
            if user_role != 'admin':
                raise ValidationError("Only users with the role 'admin' can be assigned to the 'System Admin' group.")
            if not is_staff:
                raise ValidationError("Users assigned to the 'System Admin' group must have 'is_staff' enabled.")

        if user_role == 'admin' and not is_staff:
            raise ValidationError("Users with the role 'admin' must have 'is_staff' checked.")

        if not groups:
            raise ValidationError("At least one group must be assigned to the user.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            self.save_m2m()
        return user


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = '__all__'

    readonly_fields = (
        'user_id', 'date_joined', 'date_modified', 'verified_at'  # 'email'
        'is_superuser',  # 'is_staff', 'user_role'
        'user_permissions'  # 'groups'
    )

    def clean(self):
        cleaned_data = super().clean()
        user_role = cleaned_data.get('user_role')
        groups = cleaned_data.get('groups') or []
        is_staff = cleaned_data.get('is_staff')

        system_admin_group = Group.objects.filter(name='System Admin').first()

        if system_admin_group and system_admin_group in groups:
            if user_role != 'admin':
                raise ValidationError("Only users with the role 'admin' can be assigned to the 'System Admin' group.")
            if not is_staff:
                raise ValidationError("Users assigned to the 'System Admin' group must have 'is_staff' enabled.")

        if user_role == 'admin' and not is_staff:
            raise ValidationError("Users with the role 'admin' must have 'is_staff' checked.")

        return cleaned_data


class RequiredCEAInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        has_data = any(
            form.cleaned_data and not form.cleaned_data.get('DELETE', False)
            for form in self.forms
        )

        user_role = getattr(self.instance, 'user_role', None)

        if user_role == 'cea' and not has_data:
            raise ValidationError("CEA inline data is required when user role is set to 'cea'.")

        if user_role == 'admin' and has_data:
            raise ValidationError("CEA inline must be empty when user role is set to 'admin'.")


class CareerEmplacementAdminInline(admin.StackedInline):
    model = CareerEmplacementAdmin
    can_delete = False
    verbose_name_plural = "Career Emplacement Admin Info"
    fk_name = 'user'
    formset = RequiredCEAInlineFormSet
    extra = 1


# For making Users model view only
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm
    add_form = UserAdminForm
    model = User

    list_display = ('user_id', 'status', 'user_role', 'is_staff', 'date_joined')

    ordering = ('status',)

    list_filter = ('status', 'user_role', 'is_staff', 'date_joined')

    readonly_fields = (
        'user_id', 'date_joined', 'date_modified', 'verified_at'  # 'email'
        'is_superuser',  # 'is_staff', 'user_role'
        'user_permissions'  # 'groups'
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'status', 'user_role', 'groups', 'is_staff'),
        }),
    )

    fieldsets = (
        (None, {'fields': ('email', 'user_id', 'status', 'user_role')}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('date_joined', 'date_modified', 'verified_at',)}),
    )

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == 'user_role':
            kwargs['choices'] = [('admin', 'Admin')]
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def has_add_permission(self, request):
        return True

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return True

    def get_model_perms(self, request):
        if not request.user.is_superuser:
            return {
                "add": True,
                "change": False,
                "delete": False,
                "view": False,
            }
        return super().get_model_perms(request)

    def response_add(self, request, obj, post_url_continue=None):
        if not request.user.is_superuser:
            return HttpResponseRedirect(reverse('admin:user_account_user_changelist'))
        return super().response_add(request, obj, post_url_continue)


# For displaying selected skills of applicant
@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):
    list_display = ('get_email', 'preferred_modality', 'in_practicum', 'get_date_joined')
    inlines = [InternshipRecommendationInline]

    list_filter = ('preferred_modality', 'in_practicum', DateJoinedFilter)

    exclude = ('hard_skills', 'soft_skills')

    readonly_fields = (
        'user', 'first_name', 'last_name', 'middle_initial',
        # school, department, program,
        'academic_program', 'address', 'preferred_modality',
        'quick_introduction', 'display_hard_skills', 'display_soft_skills',
        'last_matched', 'last_recommendation_filter_state', 'latitude', 'longitude'  # resume
        # enrollment_record
    )

    fieldsets = (
        (None, {
            'fields': (
                'user', 'first_name', 'last_name', 'middle_initial',
                'school', 'department', 'program',
                'academic_program', 'address', 'preferred_modality',
                'quick_introduction', 'in_practicum', 'mobile_number', 'latitude', 'longitude'
            )
        }),
        ('Skills', {
            'fields': ('display_hard_skills', 'display_soft_skills'),
        }),
        ('Documents', {
            'fields': ('resume', 'enrollment_record'),
        }),
        ('Internship Matching', {
            'fields': ('last_matched', 'tap_count', 'last_recommendation_filter_state', 'tap_count_reset'),
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
        return True

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
                'company_information', 'business_nature'
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

    def get_model_perms(self, request):
        if not request.user.is_superuser:
            return {}
        return super().get_model_perms(request)

    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'get_user_email',
        'user_role',
        'action_type',
        'model',
        'timestamp',
    )

    list_filter = ('action_type', 'timestamp')

    search_fields = ('user__email', 'model', 'object_id')

    readonly_fields = ('user', 'action', 'action_type', 'model', 'object_id', 'object_repr', 'timestamp', 'details')

    fieldsets = (
        (None, {
            'fields': (
                'user',
                'action_type',
                'action',
                'model',
                'object_id',
                'object_repr',
                'timestamp',
                'details',
            )
        }),
    )

    def get_model_perms(self, request):
        if not request.user.is_superuser:
            return {}
        return super().get_model_perms(request)

    def get_user_email(self, obj):
        if obj.user:
            return obj.user.email
        return "-"
    get_user_email.short_description = 'User Email'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True







