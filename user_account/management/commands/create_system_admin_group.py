from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from user_account.models import User, CareerEmplacementAdmin
from cea_management.models import School, Department, Program
from client_matching.models import Advertisement, Report


class Command(BaseCommand):
    help = "Creates the 'System Admin' group with specific permissions."

    def handle(self, *args, **kwargs):
        group_name = "System Admin"
        system_admin_group, created = Group.objects.get_or_create(name=group_name)

        if created:
            self.stdout.write(self.style.SUCCESS(f"Group '{group_name}' created."))
        else:
            self.stdout.write(self.style.WARNING(f"Group '{group_name}' already exists."))

        models_and_perms = [
            # (User, ['add', 'change', 'view']),
            (CareerEmplacementAdmin, ['add', 'change', 'view']),
            (School, ['add', 'change', 'view']),
            (Department, ['add', 'change', 'view']),
            (Program, ['add', 'change', 'view']),
            (Advertisement, ['add', 'change', 'view']),
            (Report, ['add', 'change', 'view']),
        ]

        for model, perms in models_and_perms:
            content_type = ContentType.objects.get_for_model(model)
            for perm in perms:
                codename = f"{perm}_{model._meta.model_name}"
                try:
                    permission = Permission.objects.get(codename=codename, content_type=content_type)
                    system_admin_group.permissions.add(permission)
                    self.stdout.write(self.style.SUCCESS(f"✓ Added permission: {codename}"))
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f"⚠ Permission not found: {codename}"))

        self.stdout.write(self.style.SUCCESS("✅ 'System Admin' group setup complete."))
