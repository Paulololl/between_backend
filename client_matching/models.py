import uuid
from decimal import Decimal
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin
from django.core.validators import MinValueValidator
from django.db import models
from storages.backends.s3boto3 import S3Boto3Storage


class HardSkillsTagList(models.Model):
    lightcast_identifier = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=500)

    def __str__(self):
        return f'{self.name}'


class SoftSkillsTagList(models.Model):
    lightcast_identifier = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=500)

    def __str__(self):
        return f'{self.name}'


class InternshipPosting(models.Model):

    internship_posting_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('user_account.Company', on_delete=models.CASCADE)
    person_in_charge = models.ForeignKey("PersonInCharge", on_delete=models.CASCADE)

    internship_position = models.CharField(max_length=100)
    address = models.CharField(max_length=255, null=True, blank=True)
    latitude = models.FloatField(default=0.0)
    longitude = models.FloatField(default=0.0)
    other_requirements = models.CharField(max_length=255, null=True, blank=True)

    is_paid_internship = models.BooleanField(default=False)
    is_only_for_practicum = models.BooleanField(default=False)

    internship_date_start = models.DateTimeField()
    ojt_hours = models.IntegerField(
        validators=[
            MinValueValidator(100)
        ]
    )
    application_deadline = models.DateTimeField(null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    required_hard_skills = models.ManyToManyField('HardSkillsTagList', related_name="required_hard_skills",
                                                  blank=True)
    required_soft_skills = models.ManyToManyField('SoftSkillsTagList', related_name="required_soft_skills",
                                                  blank=True)

    status = models.CharField(max_length=20, choices=[
        ('Open', 'Open'),
        ('Closed', 'Closed'),
        ('Expired', 'Expired'),
        ('Deleted', 'Deleted')
    ], default='Open')

    modality = models.CharField(max_length=20, choices=[
        ('Onsite', 'Onsite'),
        ('WorkFromHome', 'WorkFromHome'),
        ('Hybrid', 'Hybrid')
    ], default="Onsite")

    def __str__(self):
        return f'{self.internship_position} - {self.company.company_name}'


class InternshipRecommendation(models.Model):

    recommendation_id = models.AutoField(primary_key=True)
    applicant = models.ForeignKey('user_account.Applicant', on_delete=models.CASCADE)
    internship_posting = models.ForeignKey('InternshipPosting', on_delete=models.CASCADE)

    similarity_score = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0000'))
    time_stamp = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=[
        ('Pending', 'Pending'),
        ('Viewed', 'Viewed'),
        ('Submitted', 'Submitted'),
        ('Skipped', 'Skipped')
    ], default='Pending')

    is_current = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.recommendation_id} - {self.internship_posting}'


class Report(models.Model):

    report_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('user_account.User', on_delete=models.CASCADE, editable=False)
    internship_posting = models.ForeignKey('InternshipPosting', on_delete=models.CASCADE)

    description = models.CharField(max_length=500)

    status = models.CharField(max_length=20, choices=[
        ('Pending', 'Pending'),
        ('Solved', 'Solved'),
        ('Deleted', 'Deleted')
    ], default='Pending')

    def __str__(self):
        return f'{self.internship_posting.company.company_name} - {self.status}'


class MinQualification(models.Model):

    min_qualification_id = models.AutoField(primary_key=True)
    internship_posting = models.ForeignKey('InternshipPosting', on_delete=models.CASCADE,
                                           related_name='min_qualifications')

    min_qualification = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f'{self.min_qualification_id} - {self.min_qualification}'


class Benefit(models.Model):

    benefit_id = models.AutoField(primary_key=True)
    internship_posting = models.ForeignKey('InternshipPosting', on_delete=models.CASCADE,
                                           related_name='benefits')

    benefit = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f'{self.benefit_id} - {self.benefit}'


class Advertisement(models.Model):

    advertisement_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    image_url = models.FileField(storage=S3Boto3Storage)

    redirect_url = models.CharField(max_length=255, null=True, blank=True)
    caption_text = models.CharField(max_length=1000, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.advertisement_id} - {self.is_active}'


class KeyTask(models.Model):

    key_task_id = models.AutoField(primary_key=True)
    internship_posting = models.ForeignKey('InternshipPosting', on_delete=models.CASCADE,
                                           related_name='key_tasks')

    key_task = models.CharField(max_length=255)

    def __str__(self):
        return f'{self.key_task_id} - {self.key_task}'


class PersonInCharge(models.Model):

    person_in_charge_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('user_account.Company', on_delete=models.CASCADE)

    name = models.CharField(max_length=100)
    position = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, unique=True)
    mobile_number = models.CharField(max_length=15, null=True, blank=True)
    landline_number = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        verbose_name = "PIC"
        verbose_name_plural = "PICs"

    def __str__(self):
        return f'{self.name}'



