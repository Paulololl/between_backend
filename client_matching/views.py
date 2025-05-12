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
from rest_framework import status, generics, serializers
from rest_framework.generics import ListAPIView, CreateAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from client_matching.models import PersonInCharge, InternshipPosting
from client_matching.permissions import IsCompany
from client_matching.serializers import PersonInChargeListSerializer, CreatePersonInChargeSerializer, \
    EditPersonInChargeSerializer, BulkDeletePersonInChargeSerializer, InternshipPostingListSerializer, \
    CreateInternshipPostingSerializer, EditInternshipPostingSerializer, BulkDeleteInternshipPostingSerializer

User = get_user_model()


class InternshipPostingListView(ListAPIView):
    permission_classes = [IsAuthenticated, IsCompany]
    serializer_class = InternshipPostingListSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = InternshipPosting.objects.filter(company=user.company)
        internship_posting_id = self.request.query_params.get('internship_posting_id')
        if internship_posting_id:
            queryset = queryset.filter(internship_posting_id=internship_posting_id)
        print(self.request.user)
        return queryset


class CreateInternshipPostingView(CreateAPIView):
    queryset = InternshipPosting.objects.all()
    serializer_class = CreateInternshipPostingSerializer
    permission_classes = [IsAuthenticated, IsCompany]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class EditInternshipPostingView(APIView):
    permission_classes = [IsAuthenticated, IsCompany]

    def put(self, request):
        internship_posting_id = request.query_params.get('internship_posting_id')
        if not internship_posting_id:
            return Response({"error": "Missing 'internship_posting_id' in query parameters."},
                            status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        company = getattr(user, 'company', None)
        if not company:
            return Response({"error": "Authenticated user does not belong to any company."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            internship_posting = InternshipPosting.objects.get(
                internship_posting_id=internship_posting_id,
                company=company
            )
        except InternshipPosting.DoesNotExist:
            return Response({"error": "Internship posting not found or does not belong to your company."},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = EditInternshipPostingSerializer(
            instance=internship_posting,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PersonInChargeListView(ListAPIView):
    permission_classes = [IsAuthenticated, IsCompany]
    serializer_class = PersonInChargeListSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = PersonInCharge.objects.filter(company=user.company)

        person_in_charge_id = self.request.query_params.get('person_in_charge_id')
        if person_in_charge_id:
            queryset = queryset.filter(person_in_charge_id=person_in_charge_id)
        print(self.request.user)
        return queryset


class CreatePersonInChargeView(CreateAPIView):
    permission_classes = [IsAuthenticated, IsCompany]
    serializer_class = CreatePersonInChargeSerializer

    def get_queryset(self):
        return PersonInCharge.objects.all()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class EditPersonInChargeView(APIView):
    permission_classes = [IsAuthenticated, IsCompany]

    def put(self, request):
        pic_id = request.query_params.get('person_in_charge_id')
        if not pic_id:
            return Response({'error': 'Missing person_in_charge ID.'}, status=400)

        try:
            pic = PersonInCharge.objects.get(person_in_charge_id=pic_id)
        except PersonInCharge.DoesNotExist:
            return Response({'error': 'Person in charge not found.'}, status=404)

        serializer = EditPersonInChargeSerializer(instance=pic, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


class BulkDeletePersonInChargeView(APIView):
    permission_classes = [IsAuthenticated, IsCompany]

    def delete(self, request):
        serializer = BulkDeletePersonInChargeSerializer(data=request.data)
        if serializer.is_valid():
            pic_ids = serializer.validated_data['pic_ids']
            deleted_count, _ = PersonInCharge.objects.filter(person_in_charge_id__in=pic_ids).delete()
            return Response({
                'message': f'Successfully deleted {deleted_count} person(s) in charge.'
            }, status=status.HTTP_204_NO_CONTENT)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BulkDeleteInternshipPostingView(APIView):
    permission_classes = [IsAuthenticated, IsCompany]

    def put(self, request):
        serializer = BulkDeleteInternshipPostingSerializer(data=request.data)
        if serializer.is_valid():
            posting_ids = serializer.validated_data['posting_ids']

            updated_count = InternshipPosting.objects.filter(
                internship_posting_id__in=posting_ids,
                company=request.user.company
            ).update(status='Deleted')

            return Response(
                {"message": f"{updated_count} internship posting(s) deleted."},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


