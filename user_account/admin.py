from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (User, Applicant, Company, CareerEmplacementAdmin, OJTCoordinator)


model_to_register = [Applicant, Company, CareerEmplacementAdmin, OJTCoordinator]

for model in model_to_register:
    admin.site.register(model)


# For making Users model view only
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User

    list_display = ('email', 'user_id', 'status', 'user_role', 'is_staff', 'is_superuser')

    ordering = ('email',)

    list_filter = ('status', 'user_role', 'is_staff')

    readonly_fields = (
        'email', 'user_id', 'date_joined', 'date_modified',
        'status', 'user_role', 'is_staff', 'is_superuser',
        'groups', 'user_permissions'
    )

    fieldsets = (
        (None, {'fields': ('email', 'user_id', 'status', 'user_role')}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('date_joined', 'date_modified')}),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True


