from rest_framework import generics
from rest_framework.generics import ListAPIView, CreateAPIView

from cea_management.models import Department, Program
from .models import Applicant, School, Company, CareerEmplacementAdmin
from .serializers import (ApplicantRegisterSerializer, NestedSchoolDepartmentProgramSerializer,
                          DepartmentSerializer, ProgramNestedSerializer, SchoolSerializer, CompanyRegisterSerializer,
                          CareerEmplacementAdminRegisterSerializer)


class SchoolListView(ListAPIView):
    queryset = School.objects.all()
    serializer_class = SchoolSerializer

    def get_queryset(self):
        queryset = School.objects.all()
        school_id = self.request.query_params.get('school_id')
        if school_id:
            queryset = queryset.filter(school_id=school_id)
        return queryset


class DepartmentListView(ListAPIView):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer

    def get_queryset(self):
        queryset = Department.objects.all()
        department_id = self.request.query_params.get('department_id')
        school_id = self.request.query_params.get('school_id')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        if school_id:
            queryset = queryset.filter(school_id=school_id)
        return queryset


class ProgramListView(ListAPIView):
    queryset = Program.objects.all()
    serializer_class = ProgramNestedSerializer

    def get_queryset(self):
        queryset = Program.objects.all()
        program_id = self.request.query_params.get('program_id')
        department_id = self.request.query_params.get('department_id')
        if program_id:
            queryset = queryset.filter(program_id=program_id)
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        return queryset


class NestedSchoolDepartmentProgramListView(ListAPIView):
    queryset = School.objects.prefetch_related('departments__programs')
    serializer_class = NestedSchoolDepartmentProgramSerializer

    def get_queryset(self):
        queryset = School.objects.all()
        school_id = self.request.query_params.get('school_id')
        if school_id:
            queryset = queryset.filter(school_id=school_id)
        return queryset


class ApplicantRegisterView(CreateAPIView):
    queryset = Applicant.objects.all()
    serializer_class = ApplicantRegisterSerializer


class CompanyRegisterView(CreateAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanyRegisterSerializer


class CareerEmplacementAdminRegisterView(CreateAPIView):
    queryset = CareerEmplacementAdmin.objects.all()
    serializer_class = CareerEmplacementAdminRegisterSerializer
