from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView, CreateAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from cea_management.models import Department, Program, School
from .models import Applicant, Company, CareerEmplacementAdmin, OJTCoordinator
from .serializers import (ApplicantRegisterSerializer, NestedSchoolDepartmentProgramSerializer,
                          DepartmentSerializer, ProgramNestedSerializer, SchoolSerializer, CompanyRegisterSerializer,
                          CareerEmplacementAdminRegisterSerializer, OJTCoordinatorRegisterSerializer,
                          MyTokenObtainPairSerializer, EmailLoginSerializer, SchoolEmailCheckSerializer,
                          GetApplicantSerializer, MyTokenRefreshSerializer, SendEmailVerificationSerializer,
                          GetCompanySerializer, SendForgotPasswordLinkSerializer, ResetPasswordSerializer,
                          DeleteAccountSerializer, ChangePasswordSerializer, GetOJTCoordinatorSerializer,
                          EditCompanySerializer, EditApplicantSerializer, GetUserSerializer, GetEmailSerializer, )

User = get_user_model()


class GetUserView(ListAPIView):
    queryset = User.objects.all()
    serializer_class = GetUserSerializer

    def get_queryset(self):
        queryset = User.objects.all()
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        print(self.request.user)
        return queryset


class GetEmailView(ListAPIView):
    queryset = User.objects.all()
    serializer_class = GetEmailSerializer

    def get_queryset(self):
        queryset = User.objects.all()
        email = self.request.query_params.get('email')
        if email:
            queryset = queryset.filter(email=email)
        print(self.request.user)
        return queryset


class SchoolListView(ListAPIView):
    queryset = School.objects.all()
    serializer_class = SchoolSerializer

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


class GetApplicantView(ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Applicant.objects.all()
    serializer_class = GetApplicantSerializer

    def get_queryset(self):
        queryset = Applicant.objects.all()
        user = self.request.query_params.get('user')
        if user:
            queryset = queryset.filter(user=user)
        return queryset


class EditApplicantView(APIView):
    permission_classes = [IsAuthenticated]
    def put(self, request):
        serializer = EditApplicantSerializer(instance=request.user.applicant, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


class CompanyRegisterView(CreateAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanyRegisterSerializer


class GetCompanyView(ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Company.objects.all()
    serializer_class = GetCompanySerializer

    def get_queryset(self):
        queryset = Company.objects.all()
        user = self.request.query_params.get('user')
        if user:
            queryset = queryset.filter(user=user)
        return queryset


class EditCompanyView(APIView):
    permission_classes = [IsAuthenticated]
    def put(self, request):
        serializer = EditCompanySerializer(instance=request.user.company, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


class CareerEmplacementAdminRegisterView(CreateAPIView):
    queryset = CareerEmplacementAdmin.objects.all()
    serializer_class = CareerEmplacementAdminRegisterSerializer


class OJTCoordinatorRegisterView(CreateAPIView):
    queryset = OJTCoordinator.objects.all()
    serializer_class = OJTCoordinatorRegisterSerializer


class GetOJTCoordinatorView(ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = OJTCoordinator.objects.all()
    serializer_class = GetOJTCoordinatorSerializer

    def get_queryset(self):
        queryset = OJTCoordinator.objects.all()
        user = self.request.query_params.get('user')
        if user:
            queryset = queryset.filter(user=user)
        return queryset


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


class MyTokenRefreshView(TokenRefreshView):
    serializer_class = MyTokenRefreshSerializer


class EmailLoginView(APIView):

    @extend_schema(
        request=EmailLoginSerializer,
        responses={200: {'message': 'Email verified'}}
    )
    def post(self, request):
        serializer = EmailLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = User.objects.get(email=serializer.validated_data['email'])
            return Response({'Message': "Email is valid!",
                             'status': user.status},
                            status=status.HTTP_200_OK)
        email = request.data.get('email')
        if email:
            try:
                user = User.objects.get(email=email)
                return Response({'status': user.status}, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                return Response({'email': 'User with this email does not exist.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SchoolEmailCheckView(APIView):

    @extend_schema(
        request=SchoolEmailCheckSerializer,
        responses={200: {
            'message': 'Institutional email is valid.',
            "email": ["email"]
        }}
    )
    def post(self, request):
        serializer = SchoolEmailCheckSerializer(data=request.data)
        if serializer.is_valid():
            return Response({
                "message": "Institutional email is valid.",
                "email": serializer.validated_data["email"]
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyEmailView(APIView):
    def post(self, request):
        serializer = SendEmailVerificationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Verification email sent!"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)

            stored_token = cache.get(f"verification_token_{user.pk}")
            expiration_time = cache.get(f"verification_expiration_{user.pk}")

            if stored_token and default_token_generator.check_token(user, token) and token == stored_token:
                if timezone.now() > expiration_time:
                    return redirect(
                        'https://localhost:5173/sign-up/applicant/account-verified?status=error&reason=expired')

                user.status = 'Active'
                user.verified_at = timezone.now()
                user.save()

                if hasattr(user, 'applicant'):
                    return redirect(f'https://localhost:5173/sign-up/applicant/account-verified?'
                                    f'status=success&uuid={user.pk}')

                elif hasattr(user, 'company'):
                    return redirect(f'https://localhost:5173/sign-up/company/account-verified'
                                    f'?status=success&uuid={user.pk}')

                else:
                    return redirect(
                        f'https://localhost:5173/sign-up/account-reverify?status=invalid')
            else:
                if hasattr(user, 'applicant'):
                    return redirect(f'https://localhost:5173/sign-up/applicant/account-reverify'
                                    f'?status=invalid&uuid={user.pk}')

                elif hasattr(user, 'company'):
                    return redirect(f'https://localhost:5173/sign-up/company/account-reverify'
                                    f'?status=invalid&uuid={user.pk}')
                else:
                    return redirect(f'https://localhost:5173/sign-up/account-reverify?status=invalid')

        except (User.DoesNotExist, ValueError, TypeError):
            return redirect('https://localhost:5173/sign-up/account-reverify?status=invalid')


class ForgotPasswordLinkView(APIView):
    def post(self, request):
        serializer = SendForgotPasswordLinkSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password reset link sent successfully!"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))

            user = User.objects.get(pk=uid)

            stored_token = cache.get(f"reset_token_{user.pk}")
            expiration_time = cache.get(f"reset_expiration_{user.pk}")

            if stored_token and default_token_generator.check_token(user, token) and token == stored_token:
                if timezone.now() > expiration_time:
                    return Response({"error": "The reset link has expired."}, status=status.HTTP_400_BAD_REQUEST)
                return Response({
                    "message": "The reset link is valid.",
                    "email": user.email
                }, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Invalid or expired reset link."}, status=status.HTTP_400_BAD_REQUEST)

        except (User.DoesNotExist, ValueError, TypeError):
            return Response({"error": "Invalid or expired reset link."}, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(APIView):
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password reset successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeleteAccountView(APIView):
    def put(self, request):
        serializer = DeleteAccountSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            serializer.save()

            return Response({"message": "Account deleted successfully."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    def put(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            serializer.save()

            return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



