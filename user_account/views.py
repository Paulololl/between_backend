from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.generics import ListAPIView, CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from cea_management.models import Department, Program
from .models import Applicant, School, Company, CareerEmplacementAdmin, OJTCoordinator
from .serializers import (ApplicantRegisterSerializer, NestedSchoolDepartmentProgramSerializer,
                          DepartmentSerializer, ProgramNestedSerializer, SchoolSerializer, CompanyRegisterSerializer,
                          CareerEmplacementAdminRegisterSerializer, OJTCoordinatorRegisterSerializer,
                          MyTokenObtainPairSerializer, EmailLoginSerializer)


class SchoolListView(ListAPIView):
    queryset = School.objects.all()
    serializer_class = SchoolSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = School.objects.all()
        school_id = self.request.query_params.get('school_id')
        if school_id:
            queryset = queryset.filter(school_id=school_id)

        print(self.request.user)

        return queryset


class DepartmentListView(ListAPIView):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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


class OJTCoordinatorRegisterView(CreateAPIView):
    queryset = OJTCoordinator.objects.all()
    serializer_class = OJTCoordinatorRegisterSerializer


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


class EmailLoginView(APIView):

    @extend_schema(
        request=EmailLoginSerializer,
        responses={200: {'message': 'Email verified'}}
    )
    def post(self, request):
        serializer = EmailLoginSerializer(data=request.data)
        if serializer.is_valid():
            return Response({'Message': "Email is valid!"})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

