import json
import random
from django.db import transaction
from django.contrib.auth import get_user_model
from django.db.models import Avg, ProtectedError
from django.utils import timezone
from django.utils.timezone import now
from drf_spectacular.utils import extend_schema
from rest_framework import status, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status as drf_status

from client_application.models import Application, Notification
from client_matching.functions import run_internship_matching, fisher_yates_shuffle
from client_matching.models import PersonInCharge, InternshipPosting, InternshipRecommendation, Advertisement
from user_account.permissions import IsCompany, IsApplicant
from client_matching.serializers import PersonInChargeListSerializer, CreatePersonInChargeSerializer, \
    EditPersonInChargeSerializer, BulkDeletePersonInChargeSerializer, InternshipPostingListSerializer, \
    CreateInternshipPostingSerializer, EditInternshipPostingSerializer, BulkDeleteInternshipPostingSerializer, \
    ToggleInternshipPostingSerializer, InternshipMatchSerializer, InternshipRecommendationListSerializer, \
    UploadDocumentSerializer, ReportPostingSerializer, InPracticumSerializer
from client_matching.utils import update_internship_posting_status, delete_old_deleted_postings, \
    reset_recommendations_and_tap_count

User = get_user_model()
client_matching_tag = extend_schema(tags=["client_matching"])


@client_matching_tag
class GetInternshipPostingsView(ListAPIView):
    permission_classes = [IsAuthenticated, IsApplicant]
    serializer_class = InternshipPostingListSerializer
    queryset = InternshipPosting.objects.all()


@client_matching_tag
class InternshipPostingListView(ListAPIView):
    permission_classes = [IsAuthenticated, IsCompany]
    serializer_class = InternshipPostingListSerializer

    def get_queryset(self):
        user = self.request.user
        update_internship_posting_status(company=user.company)
        delete_old_deleted_postings()

        queryset = InternshipPosting.objects.filter(company=user.company).exclude(status='Deleted')

        internship_posting_id = self.request.query_params.get('internship_posting_id')
        if internship_posting_id:
            queryset = queryset.filter(internship_posting_id=internship_posting_id)
        print(self.request.user)

        allowed_statuses = {'Open', 'Closed', 'Expired'}
        status_param = self.request.query_params.get('status')
        if status_param:
            requested_statuses = [s.strip() for s in status_param.split(',')]
            valid_statuses = [s for s in requested_statuses if s in allowed_statuses]
            queryset = queryset.filter(status__in=valid_statuses)

        return queryset


@client_matching_tag
class CreateInternshipPostingView(CreateAPIView):
    queryset = InternshipPosting.objects.all()
    serializer_class = CreateInternshipPostingSerializer
    permission_classes = [IsAuthenticated, IsCompany]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        delete_old_deleted_postings()
        serializer.save()


@client_matching_tag
class EditInternshipPostingView(APIView):
    permission_classes = [IsAuthenticated, IsCompany]

    def put(self, request):
        delete_old_deleted_postings()

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

            related_applications = internship_posting.application_set.all()
            for application in related_applications:
                Notification.objects.create(
                    application=application,
                    notification_text=f"{company.company_name} has updated the internship information.",
                    notification_type='Applicant'
                )
                if application.applicant_status != 'Deleted':
                    application.applicant_status = 'Unread'
                    application.save(update_fields=['applicant_status'])

            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@client_matching_tag
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


@client_matching_tag
class CreatePersonInChargeView(CreateAPIView):
    permission_classes = [IsAuthenticated, IsCompany]
    serializer_class = CreatePersonInChargeSerializer

    def get_queryset(self):
        return PersonInCharge.objects.all()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


@client_matching_tag
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


@client_matching_tag
class BulkDeletePersonInChargeView(APIView):
    permission_classes = [IsAuthenticated, IsCompany]

    @transaction.atomic
    def delete(self, request):
        serializer = BulkDeletePersonInChargeSerializer(data=request.data)
        if serializer.is_valid():
            pic_ids = serializer.validated_data['pic_ids']
            queryset = PersonInCharge.objects.filter(
                person_in_charge_id__in=pic_ids,
                company=request.user.company,
            )
            try:
                deleted_count, _ = queryset.delete()
                return Response({
                    'message': f'Successfully deleted {deleted_count} person(s) in charge.'
                }, status=status.HTTP_204_NO_CONTENT)

            except ProtectedError as e:
                protected_emails = list({
                    obj.email
                    for obj in e.protected_objects
                    if isinstance(obj, PersonInCharge) and obj.email
                })
                raise ValidationError({
                    'error': 'Some PIC/s could not be deleted '
                             'because they are assigned to internship postings.',
                    'protected_emails': protected_emails
                })

            except Exception as e:
                raise ValidationError({
                    'error': f'An unexpected error occurred: {str(e)}'
                })

        raise ValidationError(serializer.errors)


@client_matching_tag
class BulkDeleteInternshipPostingView(APIView):
    permission_classes = [IsAuthenticated, IsCompany]

    @transaction.atomic
    def put(self, request):
        serializer = BulkDeleteInternshipPostingSerializer(data=request.data)
        if serializer.is_valid():
            posting_ids = serializer.validated_data['posting_ids']

            updated_count = InternshipPosting.objects.filter(
                internship_posting_id__in=posting_ids,
                company=request.user.company
            ).update(
                status='Deleted',
                date_modified=now()
            )

            return Response(
                {"message": f"{updated_count} internship posting(s) deleted."},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@client_matching_tag
class ToggleInternshipPostingView(APIView):
    permission_classes = [IsAuthenticated, IsCompany]

    def put(self, request):
        internship_posting_id = request.query_params.get('internship_posting_id')
        if not internship_posting_id:
            return Response(
                {"error": "Missing internship_posting_id in query parameters."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ToggleInternshipPostingSerializer(data=request.data)
        if serializer.is_valid():
            new_status = serializer.validated_data.get('status')

            try:
                posting = InternshipPosting.objects.get(
                    internship_posting_id=internship_posting_id,
                    company=request.user.company,
                    status__in=['Open', 'Closed']
                )
            except InternshipPosting.DoesNotExist:
                return Response(
                    {"error": "Internship posting not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            posting.status = new_status
            posting.save()

            return Response(
                {"message": f"Internship posting status changed to '{new_status}'."},
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@client_matching_tag
class InternshipMatchView(APIView):
    permission_classes = [IsAuthenticated, IsApplicant]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        user = request.user

        try:
            applicant = user.applicant
        except AttributeError:
            raise serializers.ValidationError({'error': 'Applicant profile not found for the current user.'})

        serializer = InternshipMatchSerializer(data=request.data, context={'applicant': applicant})
        if serializer.is_valid():
            ranked_result = serializer.save()

            return Response(ranked_result, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@client_matching_tag
class InternshipRecommendationListView(ListAPIView):
    permission_classes = [IsAuthenticated, IsApplicant]
    serializer_class = InternshipRecommendationListSerializer

    def parse_bool(self, value, field_name):
        true_vals = ['true', 'yes']
        false_vals = ['false', 'no']
        value_lower = value.lower()

        if value_lower in true_vals:
            return True
        elif value_lower in false_vals:
            return False
        else:
            raise ValidationError({field_name: f"Invalid value '{value}'. Use 'yes'/'no' or 'true'/'false'."})

    def get_filter_state(self):
        applicant = self.request.user.applicant

        if applicant.in_practicum != 'Yes':
            return {
                'is_paid_internship': None,
                'is_only_for_practicum': None,
                'modality': None
            }

        is_paid_internship = self.request.query_params.get('is_paid_internship')
        is_only_for_practicum = self.request.query_params.get('is_only_for_practicum')
        modality = self.request.query_params.get('modality')

        if is_paid_internship is not None:
            is_paid_internship = self.parse_bool(is_paid_internship, 'is_paid_internship')
        if is_only_for_practicum is not None:
            is_only_for_practicum = self.parse_bool(is_only_for_practicum, 'is_only_for_practicum')

        return {
            'is_paid_internship': is_paid_internship,
            'is_only_for_practicum': is_only_for_practicum,
            'modality': modality or None
        }

    def get_queryset(self):
        applicant = self.request.user.applicant
        reset_recommendations_and_tap_count(applicant)
        run_internship_matching(applicant)

        filter_state = self.get_filter_state()
        json.dumps(filter_state, sort_keys=True)
        self.filter_state = filter_state

        open_posting_ids = InternshipPosting.objects.filter(status='Open') \
            .values_list('internship_posting_id', flat=True)

        base_queryset = InternshipRecommendation.objects.filter(
            applicant=applicant,
            status='Pending',
            internship_posting_id__in=open_posting_ids
        )

        if applicant.in_practicum == 'Yes':
            if filter_state['is_paid_internship'] is not None:
                base_queryset = base_queryset.filter(
                    internship_posting__is_paid_internship=filter_state['is_paid_internship'])

            if filter_state['is_only_for_practicum'] is not None:
                base_queryset = base_queryset.filter(
                    internship_posting__is_only_for_practicum=filter_state['is_only_for_practicum'])

            if filter_state['modality']:
                base_queryset = base_queryset.filter(internship_posting__modality=filter_state['modality'])

        elif any([
            filter_state['is_paid_internship'] is not None,
            filter_state['is_only_for_practicum'] is not None,
            filter_state['modality']
        ]):
            self.filter_state = {
                'is_paid_internship': None,
                'is_only_for_practicum': None,
                'modality': None
            }
            raise ValidationError({'error': 'You must be in practicum to apply internship filters.'})

        avg_score = base_queryset.aggregate(avg=Avg('similarity_score'))['avg'] or 0

        current_pending = InternshipRecommendation.objects.filter(
            applicant=applicant,
            is_current=True,
            internship_posting__status='Open'
        ).first()

        if current_pending:
            return [current_pending]

        if base_queryset.exists():
            InternshipRecommendation.objects.filter(applicant=applicant, is_current=True).update(is_current=False)
            current_pending = random.choice(list(base_queryset))
            current_pending.is_current = True
            current_pending.save()

            applicant.last_recommendation_filter_state = filter_state
            applicant.save(update_fields=['last_recommendation_filter_state'])

        rest_queryset = base_queryset.exclude(pk=current_pending.pk) if current_pending else base_queryset
        rest_queryset = rest_queryset.filter(similarity_score__gte=avg_score).distinct()

        rest_list = list(rest_queryset)
        rest_list = fisher_yates_shuffle(rest_list)

        final_list = [current_pending] + rest_list if current_pending else rest_list
        return final_list

    def list(self, request, *args, **kwargs):
        applicant = request.user.applicant

        if applicant.tap_count >= 10:
            return Response(
                {'message': 'You have already reached your daily limit. Come back again tomorrow!'},
                status=status.HTTP_200_OK
            )

        filter_state = self.get_filter_state()
        last_filter_state = applicant.last_recommendation_filter_state or {}
        filters_changed = (filter_state != last_filter_state)
        apply_ad_chance = not filters_changed

        if apply_ad_chance:
            advertisement_chance = 0.25
            show_ad = random.random() < advertisement_chance
            if show_ad:
                ad = Advertisement.objects.order_by('?').first()
                if ad:
                    ad_data = {
                        "advertisement_id": str(ad.advertisement_id),
                        "image_url": ad.image_url.url if ad.image_url else None,
                        "redirect_url": ad.redirect_url,
                        "caption_text": ad.caption_text,
                        "created_at": ad.created_at.isoformat()
                    }
                    return Response([ad_data])
                # else:
                #     return Response({"detail": "No advertisement found."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            queryset = self.get_queryset()
        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        is_only_for_practicum = self.filter_state.get('is_only_for_practicum')

        if not queryset and is_only_for_practicum is not None:
            if is_only_for_practicum is True:
                return Response(
                    {'message': 'You have viewed all internship recommendations with Practicum Filtering set to "Yes".'},
                    status=status.HTTP_200_OK
                )
            elif is_only_for_practicum is False:
                return Response(
                    {'message': 'You have viewed all internship recommendations with Practicum Filtering set to "No".'},
                    status=status.HTTP_200_OK
                )

        if queryset:
            serializer = self.get_serializer(queryset[:1], many=True)
            return Response(serializer.data)

        return Response([], status=status.HTTP_200_OK)


@client_matching_tag
class InternshipRecommendationTapView(APIView):
    permission_classes = [IsAuthenticated, IsApplicant]

    @transaction.atomic
    def put(self, request):
        recommendation_id = request.query_params.get('recommendation_id')
        status_param = request.query_params.get('status')
        normalized_status = status_param.capitalize() if status_param else None

        if not recommendation_id:
            return Response(
                {'error': 'Missing "recommendation_id" parameter.'},
                status=drf_status.HTTP_400_BAD_REQUEST
            )

        if normalized_status not in ['Skipped', 'Submitted']:
            return Response(
                {'error': 'Invalid or missing "status" parameter. Must be either "Skipped" or "Submitted".'},
                status=drf_status.HTTP_400_BAD_REQUEST
            )

        applicant = request.user.applicant
        reset_recommendations_and_tap_count(applicant)
        run_internship_matching(applicant)

        open_posting_ids = InternshipPosting.objects.filter(status='Open') \
            .values_list('internship_posting_id', flat=True)

        try:
            recommendation = InternshipRecommendation.objects.get(
                pk=recommendation_id,
                applicant=applicant,
                status='Pending',
                internship_posting_id__in=open_posting_ids
            )
        except InternshipRecommendation.DoesNotExist:
            return Response(
                {'error': 'Recommendation not found, not pending, or not for an open internship posting.'},
                status=drf_status.HTTP_400_BAD_REQUEST
            )

        recommendation.status = normalized_status
        recommendation.time_stamp = timezone.now()
        recommendation.is_current = False
        recommendation.save()

        applicant.tap_count = (applicant.tap_count or 0) + 1
        applicant.save()

        if normalized_status == 'Submitted':
            Application.objects.create(
                applicant=applicant,
                internship_posting=recommendation.internship_posting,
                status='Pending',
                is_bookmarked=True
            )

        return Response(
            {
                'recommendation_id': recommendation.recommendation_id,
                'updated_status': recommendation.status
            },
            status=drf_status.HTTP_200_OK
        )


@client_matching_tag
class UploadDocumentView(APIView):
    permission_classes = [IsAuthenticated, IsApplicant]

    def put(self, request):
        serializer = UploadDocumentSerializer(instance=request.user.applicant, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def get(self, request):
        serializer = UploadDocumentSerializer(instance=request.user.applicant, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


@client_matching_tag
class InPracticumView(APIView):
    permission_classes = [IsAuthenticated, IsApplicant]

    def get(self, request):
        serializer = InPracticumSerializer(instance=request.user.applicant, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


@client_matching_tag
class ReportPostingView(CreateAPIView):
    permission_classes = [IsAuthenticated, IsApplicant]
    serializer_class = ReportPostingSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context








