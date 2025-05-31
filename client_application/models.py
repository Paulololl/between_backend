import uuid
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin
from django.db import models


class Application(models.Model):

    application_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.ForeignKey('user_account.Applicant', on_delete=models.CASCADE)
    internship_posting = models.ForeignKey('client_matching.InternshipPosting', on_delete=models.CASCADE)

    application_date = models.DateTimeField(auto_now_add=True)

    status = models.CharField(max_length=20, choices=[
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Rejected', 'Rejected'),
        ('Dropped', 'Dropped')
    ], default='Pending')

    is_bookmarked = models.BooleanField(default=True)
    applicant_status = models.CharField(max_length=20, choices=[
        ('Read', 'Read'),
        ('Unread', 'Unread'),
        ('Deleted', 'Deleted'),
    ], default='Unread')
    company_status = models.CharField(max_length=20, choices=[
        ('Read', 'Read'),
        ('Unread', 'Unread'),
        ('Deleted', 'Deleted'),
    ], default='Unread')

    def __str__(self):
        return (f'{self.application_id} - {self.internship_posting.internship_position} - {self.applicant.first_name}'
                f' {self.applicant.last_name} - {self.status}')


class Endorsement(models.Model):

    endorsement_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ojt_coordinator = models.ForeignKey('user_account.OJTCoordinator', on_delete=models.CASCADE)
    application = models.ForeignKey('Application', on_delete=models.CASCADE)

    comments = models.CharField(max_length=500, null=True, blank=True)
    date_approved = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=[
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected')
    ], default='Pending')

    def __str__(self):
        return (f'{self.endorsement_id} {self.application.applicant.first_name}'
                f' {self.application.applicant.last_name} - {self.status}')


class Notification(models.Model):

    notification_id = models.AutoField(primary_key=True)
    application = models.ForeignKey('Application', on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)

    notification_text = models.CharField(max_length=300)

    notification_type = models.CharField(max_length=20, choices=[
        ('Applicant', 'Applicant'),
        ('Company', 'Company')
    ])

    def __str__(self):
        return f'{self.notification_id} - {self.application.application_id} - {self.notification_type}'




