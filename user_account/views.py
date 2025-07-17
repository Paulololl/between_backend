from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.db import transaction
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.utils.timezone import now
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from cea_management.models import Department, Program, School
from client_matching.functions import run_internship_matching
from user_account.permissions import IsApplicant, IsCoordinator
from client_matching.serializers import InternshipMatchSerializer
from client_matching.utils import reset_recommendations_and_tap_count
from .models import Applicant, Company, CareerEmplacementAdmin, OJTCoordinator
from .serializers import (ApplicantRegisterSerializer, NestedSchoolDepartmentProgramSerializer,
                          DepartmentSerializer, ProgramNestedSerializer, SchoolSerializer, CompanyRegisterSerializer,
                          CareerEmplacementAdminRegisterSerializer, OJTCoordinatorRegisterSerializer,
                          MyTokenObtainPairSerializer, EmailLoginSerializer, SchoolEmailCheckSerializer,
                          GetApplicantSerializer, MyTokenRefreshSerializer, SendEmailVerificationSerializer,
                          GetCompanySerializer, SendForgotPasswordLinkSerializer, ResetPasswordSerializer,
                          DeleteAccountSerializer, ChangePasswordSerializer, GetOJTCoordinatorSerializer,
                          EditCompanySerializer, EditApplicantSerializer, GetUserSerializer, GetEmailSerializer, )
from .utils import delete_pending_users

User = get_user_model()
user_account_tag = extend_schema(tags=["user_account"])


@user_account_tag
class GetUserView(ListAPIView):
    queryset = User.objects.all()
    serializer_class = GetUserSerializer

    def get_queryset(self):
        delete_pending_users()

        queryset = User.objects.all()
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        print(self.request.user)
        return queryset


@user_account_tag
class GetEmailView(ListAPIView):
    queryset = User.objects.all()
    serializer_class = GetEmailSerializer

    def get_queryset(self):
        delete_pending_users()

        queryset = User.objects.all()
        email = self.request.query_params.get('email')
        if email:
            queryset = queryset.filter(email=email)
        print(self.request.user)
        return queryset


@user_account_tag
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


@user_account_tag
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


@user_account_tag
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


@user_account_tag
class NestedSchoolDepartmentProgramListView(ListAPIView):
    queryset = School.objects.prefetch_related('departments__programs')
    serializer_class = NestedSchoolDepartmentProgramSerializer

    def get_queryset(self):
        queryset = School.objects.all()
        school_id = self.request.query_params.get('school_id')
        if school_id:
            queryset = queryset.filter(school_id=school_id)
        return queryset


@user_account_tag
class ApplicantRegisterView(CreateAPIView):
    queryset = Applicant.objects.all()
    serializer_class = ApplicantRegisterSerializer


@user_account_tag
class GetApplicantView(ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Applicant.objects.all()
    serializer_class = GetApplicantSerializer

    def get_queryset(self):
        delete_pending_users()

        queryset = Applicant.objects.all()
        user = self.request.query_params.get('user')
        if user:
            queryset = queryset.filter(user=user)
        return queryset


@user_account_tag
class EditApplicantView(APIView):
    permission_classes = [IsAuthenticated, IsApplicant]

    def put(self, request):
        applicant = request.user.applicant
        serializer = EditApplicantSerializer(instance=applicant, data=request.data, partial=True)

        if serializer.is_valid():
            with transaction.atomic():
                applicant.user.date_modified = timezone.now()
                applicant.user.save(update_fields=['date_modified'])
                serializer.save()

            run_internship_matching(applicant)

            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@user_account_tag
class CompanyRegisterView(CreateAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanyRegisterSerializer


@user_account_tag
class GetCompanyView(ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Company.objects.all()
    serializer_class = GetCompanySerializer

    def get_queryset(self):
        delete_pending_users()

        queryset = Company.objects.all()
        user = self.request.query_params.get('user')
        if user:
            queryset = queryset.filter(user=user)
        return queryset


@user_account_tag
class EditCompanyView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request):
        serializer = EditCompanySerializer(instance=request.user.company, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


@user_account_tag
class CareerEmplacementAdminRegisterView(CreateAPIView):
    queryset = CareerEmplacementAdmin.objects.all()
    serializer_class = CareerEmplacementAdminRegisterSerializer


@user_account_tag
class OJTCoordinatorRegisterView(CreateAPIView):
    queryset = OJTCoordinator.objects.all()
    serializer_class = OJTCoordinatorRegisterSerializer


@user_account_tag
class GetOJTCoordinatorView(ListAPIView):
    permission_classes = [IsAuthenticated, IsCoordinator]
    queryset = OJTCoordinator.objects.all()
    serializer_class = GetOJTCoordinatorSerializer

    def get_queryset(self):
        delete_pending_users()
        user = self.request.user
        if user.user_role != 'coordinator':
            raise ValidationError({'error': "User must be an OJT Coordinator."})

        return OJTCoordinator.objects.filter(user=user)


@user_account_tag
class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        user = None
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.user
        except ValidationError:
            pass

        response = super().post(request, *args, **kwargs)

        # if response.status_code == 200 and user and hasattr(user, 'applicant'):
        #     serializer = InternshipMatchSerializer(context={'applicant': user.applicant})
        #     serializer.create(validated_data={})
        #     reset_recommendations_and_tap_count(user.applicant)
        #     run_internship_matching(user.applicant)

        return response


@user_account_tag
class MyTokenRefreshView(TokenRefreshView):
    serializer_class = MyTokenRefreshSerializer


@user_account_tag
class EmailLoginView(APIView):

    @extend_schema(
        request=EmailLoginSerializer,
        responses={200: {'message': 'Email verified'}}
    )
    @transaction.atomic
    def post(self, request):
        delete_pending_users()

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

                if user.status == 'Deleted':
                    return Response({'email': 'User with this email does not exist.'},
                                    status=status.HTTP_400_BAD_REQUEST)

                if user.status == 'Inactive':
                    return Response({'email': 'User with this email does not exist.'},
                                    status=status.HTTP_400_BAD_REQUEST)

                if user.status == 'Suspended':
                    return Response({'email': 'Email is Suspended. Please try again.'},
                                    status=status.HTTP_400_BAD_REQUEST)

                return Response({'status': user.status}, status=status.HTTP_200_OK)

            except User.DoesNotExist:
                return Response({'email': 'User with this email does not exist.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@user_account_tag
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


@user_account_tag
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
                        'https://between-project-web.vercel.app/sign-up/applicant/account-verified?status=invalid')

                user.status = 'Active'
                user.verified_at = timezone.now()
                user.save()

                if hasattr(user, 'applicant'):
                    applicant = user.applicant

                    if applicant.enrollment_record and applicant.in_practicum != 'Pending':
                        applicant.in_practicum = 'Pending'
                        applicant.save(update_fields=['in_practicum'])

                        try:
                            coordinator = OJTCoordinator.objects.get(
                                program=applicant.program,
                                user__status='Active'
                            )

                            full_name = f"{applicant.first_name} {applicant.last_name}"
                            subject = f'New Practicum Request from {full_name}'
                            html_message = (
                                f'A new practicum request has been submitted by <strong>{full_name}</strong>.<br><br>'
                                'Please log in to Between IMS to review the request.<br><br>'
                                'Best regards,<br><strong>Between Team</strong>'
                            )

                            email = EmailMessage(
                                subject=subject,
                                body=html_message,
                                from_email='Between_IMS <no-reply.between.internships@gmail.com>',
                                to=[coordinator.user.email]
                            )
                            email.content_subtype = "html"
                            email.send()

                        except OJTCoordinator.DoesNotExist:
                            pass

                    return redirect(f'https://between-project-web.vercel.app/sign-up/applicant/account-verified?'
                                    f'status=success&uuid={user.pk}')

                elif hasattr(user, 'company') or hasattr(user, 'coordinator') or hasattr(user, 'cea'):
                    return redirect(f'https://between-project-web.vercel.app/sign-up/company/account-verified'
                                    f'?status=success&uuid={user.pk}')

                else:
                    return redirect(
                        f'https://between-project-web.vercel.app/sign-up/account-reverify?status=invalid')
            else:
                if hasattr(user, 'applicant'):
                    return redirect(f'https://between-project-web.vercel.app/sign-up/applicant/account-reverify'
                                    f'?status=invalid&uuid={user.pk}')

                elif hasattr(user, 'company'):
                    return redirect(f'https://between-project-web.vercel.app/sign-up/company/account-reverify'
                                    f'?status=invalid&uuid={user.pk}')
                else:
                    return redirect(f'https://between-project-web.vercel.app/sign-up/account-reverify?status=invalid')

        except (User.DoesNotExist, ValueError, TypeError):
            return redirect(f'https://between-project-web.vercel.app/sign-up/account-reverify?status=invalid')


@user_account_tag
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


@user_account_tag
class ResetPasswordView(APIView):

    @transaction.atomic
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password reset successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@user_account_tag
class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request):
        serializer = DeleteAccountSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            serializer.save()

            return Response({"message": "Account deleted successfully."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@user_account_tag
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            serializer.save()

            return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




