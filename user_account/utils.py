from datetime import timedelta

from django.utils.timezone import now

from user_account.models import User


def delete_pending_users():
    threshold = now() - timedelta(days=3)
    User.objects.filter(status='Pending', date_joined__lt=threshold).delete()