import uuid
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin
from django.db import models


class SchoolPartnershipList(models.Model):

    school = models.ForeignKey('School', on_delete=models.CASCADE)
    company = models.ForeignKey('user_account.Company', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('school', 'company')
        verbose_name = 'School Partnership'
        verbose_name_plural = 'School Partnerships'

    def __str__(self):
        return f'{self.school.school_name} - {self.company.company_name}'


class Department(models.Model):

    department_id = models.AutoField(primary_key=True)
    school = models.ForeignKey('School', related_name='departments', on_delete=models.CASCADE)

    department_name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('school', 'department_name')

    def __str__(self):
        return f'{self.department_name}'


class Program(models.Model):

    program_id = models.AutoField(primary_key=True)
    department = models.ForeignKey('Department', related_name='programs', on_delete=models.CASCADE)

    program_name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('department', 'program_name')

    def __str__(self):
        return f'{self.program_name}'


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


