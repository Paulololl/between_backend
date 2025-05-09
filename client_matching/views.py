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

from client_matching.models import PersonInCharge
from client_matching.serializers import PersonInChargeListSerializer, CreatePersonInChargeSerializer, \
    EditPersonInChargeSerializer, BulkDeletePersonInChargeSerializer

User = get_user_model()


class PersonInChargeListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = PersonInCharge.objects.all()
    serializer_class = PersonInChargeListSerializer

    def get_queryset(self):
        queryset = PersonInCharge.objects.all()
        person_in_charge_id = self.request.query_params.get('person_in_charge_id')
        if person_in_charge_id:
            queryset = queryset.filter(person_in_charge_id=person_in_charge_id)
        print(self.request.user)
        return queryset


class CreatePersonInChargeView(CreateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = PersonInCharge.objects.all()
    serializer_class = CreatePersonInChargeSerializer


class EditPersonInChargeView(APIView):
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        serializer = BulkDeletePersonInChargeSerializer(data=request.data)
        if serializer.is_valid():
            pic_ids = serializer.validated_data['pic_ids']
            deleted_count, _ = PersonInCharge.objects.filter(person_in_charge_id__in=pic_ids).delete()
            return Response({
                'message': f'Successfully deleted {deleted_count} person(s) in charge.'
            }, status=status.HTTP_204_NO_CONTENT)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

