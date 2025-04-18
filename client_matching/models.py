import uuid
from decimal import Decimal
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin
from django.db import models
from storages.backends.s3boto3 import S3Boto3Storage


class HardSkillsTagList(models.Model):

    hard_skills_tag_id = models.AutoField(primary_key=True)
    applicant = models.ForeignKey('user_account.Applicant', on_delete=models.CASCADE)

    lightcast_identifier = models.CharField(max_length=20)
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('applicant', 'lightcast_identifier')

    def __str__(self):
        return f'{self.name} ({self.applicant.applicant_id})'


class SoftSkillsTagList(models.Model):

    soft_skills_tag_id = models.AutoField(primary_key=True)
    applicant = models.ForeignKey('user_account.Applicant', on_delete=models.CASCADE)

    lightcast_identifier = models.CharField(max_length=20)
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('applicant', 'lightcast_identifier')

    def __str__(self):
        return f'{self.name} ({self.applicant.applicant_id})'


class InternshipPosting(models.Model):

    internship_posting_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('user_account.Company', on_delete=models.CASCADE)
    person_in_charge = models.OneToOneField("PersonInCharge", on_delete=models.CASCADE)

    internship_position = models.CharField(max_length=100)
    address = models.CharField(max_length=255, null=True, blank=True)
    other_requirements = models.CharField(max_length=255, null=True, blank=True)

    is_paid_internship = models.BooleanField(default=False)
    is_only_for_practicum = models.BooleanField(default=False)

    internship_date_start = models.DateTimeField()
    ojt_hours = models.IntegerField()
    application_deadline = models.DateTimeField(null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    status = models.CharField(max_length=20, choices=[
        ('Open', 'Open'),
        ('Closed', 'Closed'),
        ('Expired', 'Expired')
    ], default='Open')

    modality = models.CharField(max_length=20, choices=[
        ('Onsite', 'Onsite'),
        ('Online', 'Online'),
        ('Hybrid', 'Hybrid')
    ], default='Onsite')

    def __str__(self):
        return f'{self.internship_posting_id} - {self.company.company_name}'


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

    def __str__(self):
        return (f'{self.recommendation_id} - {self.applicant.first_name} {self.applicant.last_name}'
                f' - {self.status}')


class Report(models.Model):

    report_id = models.AutoField(primary_key=True)
    internship_posting = models.ForeignKey('InternshipPosting', on_delete=models.CASCADE)

    description = models.CharField(max_length=500)

    status = models.CharField(max_length=20, choices=[
        ('Pending', 'Pending'),
        ('Solved', 'Solved'),
        ('Deleted', 'Deleted')
    ], default='Pending')

    def __str__(self):
        return f'{self.report_id} - {self.status}'


class MinQualification(models.Model):

    min_qualification_id = models.AutoField(primary_key=True)
    internship_posting = models.ForeignKey('InternshipPosting', on_delete=models.CASCADE)

    min_qualifications = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f'{self.min_qualification_id} - {self.internship_posting.internship_position}'


class Benefit(models.Model):

    benefit_id = models.AutoField(primary_key=True)
    internship_posting = models.ForeignKey('InternshipPosting', on_delete=models.CASCADE)

    benefits = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f'{self.benefit_id} - {self.internship_posting.internship_position}'


class Advertisement(models.Model):

    advertisement_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    image_url = models.FileField(storage=S3Boto3Storage)

    redirect_url = models.CharField(max_length=255, null=True, blank=True)
    caption_text = models.CharField(max_length=1000, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.advertisement_id} - {self.is_active}'


class RequiredHardSkill(models.Model):

    required_hard_skill_id = models.AutoField(primary_key=True)
    internship_posting = models.ForeignKey('InternshipPosting', on_delete=models.CASCADE)

    name = models.CharField(max_length=100)

    lightcast_identifier = models.CharField(max_length=20)

    class Meta:
        unique_together = ('internship_posting', 'lightcast_identifier')

    def __str__(self):
        return f'{self.required_hard_skill_id} - {self.name} ({self.internship_posting.id})'


class RequiredSoftSkill(models.Model):

    required_soft_skill_id = models.AutoField(primary_key=True)
    internship_posting = models.ForeignKey('InternshipPosting', on_delete=models.CASCADE)

    name = models.CharField(max_length=100)

    lightcast_identifier = models.CharField(max_length=20)

    class Meta:
        unique_together = ('internship_posting', 'lightcast_identifier')

    def __str__(self):
        return f'{self.required_soft_skill_id} - {self.name} ({self.internship_posting.id})'


class KeyTask(models.Model):

    key_task_id = models.AutoField(primary_key=True)
    internship_posting = models.ForeignKey('InternshipPosting', on_delete=models.CASCADE)

    key_tasks = models.CharField(max_length=100)

    def __str__(self):
        return str(self.key_task_id)


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
        return f'{self.name} - {self.position}'



