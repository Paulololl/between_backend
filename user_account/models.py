import uuid
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin
from django.db import models
from storages.backends.s3boto3 import S3Boto3Storage


class UserManager(BaseUserManager):
    def create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField(max_length=100, unique=True)
    password = models.CharField(max_length=255)

    date_joined = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    status = models.CharField(max_length=20, choices=[
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
        ('Deleted', 'Deleted'),
        ('Pending', 'Pending')
    ], default='Pending')

    user_role = models.CharField(max_length=20, choices=[
        ('ADMIN', 'Admin'),
        ('APPLICANT', 'Applicant'),
        ('COMPANY', 'Company'),
        ('CEA', 'CEA'),
        ('OJT_COORDINATOR', 'OJT_Coordinator'),
    ], default='ADMIN')

    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_groups',
        blank=True
    )

    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_permissions',
        blank=True
    )

    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f'{self.email} | {self.user_id}'


def applicant_resume_upload_path(instance, filename):
    return f'Applicant/{instance.user.email} | {str(instance.user.user_id)[-12:]}/resume/{filename}'


def applicant_enrollment_record_upload_path(instance, filename):
    return f'Applicant/{instance.user.email} | {str(instance.user.user_id)[-12:]}/enrollment_record/{filename}'


class Applicant(models.Model):
    applicant_id = models.AutoField(primary_key=True)
    user = models.OneToOneField('User', on_delete=models.CASCADE)
    school = models.ForeignKey('School', on_delete=models.CASCADE, null=True, blank=True)
    department = models.ForeignKey('cea_management.Department', on_delete=models.CASCADE, null=True, blank=True)
    program = models.ForeignKey('cea_management.Program', on_delete=models.CASCADE, null=True, blank=True)

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_initial = models.CharField(max_length=20, null=True, blank=True)
    address = models.CharField(max_length=255)

    in_practicum = models.CharField(max_length=20, choices=[
        ('No', 'No'),
        ('Pending', 'Pending'),
        ('Yes', 'Yes')
    ], default="No")

    preferred_modality = models.CharField(max_length=20, choices=[
        ('Onsite', 'Onsite'),
        ('Online', 'Online'),
        ('Hybrid', 'Hybrid')
    ], default="Onsite")

    academic_program = models.CharField(max_length=100, null=True, blank=True)
    quick_introduction = models.CharField(max_length=500, null=True, blank=True)

    resume = models.FileField(storage=S3Boto3Storage, upload_to=applicant_resume_upload_path)
    enrollment_record = models.FileField(storage=S3Boto3Storage,upload_to=applicant_enrollment_record_upload_path,
                                         null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} {self.middle_initial}"


class Company(models.Model):
    company_id = models.AutoField(primary_key=True)
    user = models.OneToOneField('User', on_delete=models.CASCADE, editable=False)

    company_name = models.CharField(max_length=255)
    company_address = models.CharField(max_length=255)
    company_information = models.CharField(max_length=1000)
    business_nature = models.CharField(max_length=100)

    company_website_url = models.CharField(max_length=255, null=True, blank=True)
    linkedin_url = models.CharField(max_length=255, null=True, blank=True)
    facebook_url = models.CharField(max_length=255, null=True, blank=True)
    instagram_url = models.CharField(max_length=255, null=True, blank=True)
    x_url = models.CharField(max_length=255, null=True, blank=True)
    other_url = models.CharField(max_length=255, null=True, blank=True)

    background_image = models.FileField(storage=S3Boto3Storage, blank=True)
    profile_picture = models.FileField(storage=S3Boto3Storage, blank=True)

    def __str__(self):
        return self.company_name


class CareerEmplacementAdmin(models.Model):
    cea_id = models.AutoField(primary_key=True)
    user = models.OneToOneField('User', on_delete=models.CASCADE, editable=False)
    school = models.ForeignKey('School', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'CEA'
        verbose_name_plural = 'CEAs'

    def __str__(self):
        return f'{self.cea_id} - {self.school.school_name}'


class OJTCoordinator(models.Model):
    ojt_coordinator_id = models.AutoField(primary_key=True)
    user = models.OneToOneField('User', on_delete=models.CASCADE, editable=False)
    program = models.OneToOneField('cea_management.Program', on_delete=models.CASCADE)

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_initial = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        verbose_name = 'OJT Coordinator'
        verbose_name_plural = 'OJT Coordinators'

    def __str__(self):
        return f'{self.first_name} {self.last_name} - {self.program.department.school.school_name}'


class School(models.Model):
    school_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    school_name = models.CharField(max_length=255, unique=True)
    school_acronym = models.CharField(max_length=10, null=True, blank=True)
    school_address = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)

    date_joined = models.DateTimeField(auto_now_add=True)

    status = models.CharField(max_length=20, choices=[
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
        ('Pending', 'Pending'),
        ('Deleted', 'Deleted'),
    ], default="Pending")

    def __str__(self):
        return self.school_name
