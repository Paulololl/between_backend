from datetime import timedelta

from django.utils.timezone import now
from rest_framework import serializers

from user_account.models import User


def delete_pending_users():
    threshold = now() - timedelta(days=3)
    User.objects.filter(status='Pending', date_joined__lt=threshold).delete()


def validate_file_size(file, max_size_mb=5):
    limit = max_size_mb * 1024 * 1024
    if file.size > limit:
        raise serializers.ValidationError(f"File size must not exceed {max_size_mb} MB.")