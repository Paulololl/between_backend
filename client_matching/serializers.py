import json
import os
from datetime import timedelta

from django.core.cache import cache
from jwt.exceptions import ExpiredSignatureError, DecodeError, InvalidTokenError
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError

from user_account.models import Company
import googlemaps
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from googlemaps import Client
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
import requests
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from between_ims import settings
from cea_management.models import Program, Department, School
from client_matching.models import PersonInCharge, InternshipPosting, KeyTask, MinQualification, Benefit, \
    HardSkillsTagList, SoftSkillsTagList
from django.core.exceptions import ValidationError

load_dotenv()


# Geopy
def get_coordinates(location):
    geolocator = Nominatim(user_agent="abcd")
    try:
        location = geolocator.geocode(location)
        if location:
            return {'lat': location.latitude, 'lng': location.longitude}
        else:
            print('error: Unable to get the location')
            return None
    except Exception as e:
        print(f'Exception: {e}')
        return None


# Google Maps
# def get_google_coordinates(location):
#     gmaps = googlemaps.Client(key=os.getenv('GOOGLEMAPS_API_KEY'))
#
#     try:
#         location = gmaps.geocode(location)  # type: ignore[attr-defined]
#         if location:
#             latitude = location[0]['geometry']['location']['lat']
#             longitude = location[0]['geometry']['location']['lng']
#             return latitude, longitude
#         else:
#             print('Error: Unable to get the location')
#             return None
#     except Exception as e:
#         print(f'Exception: {e}')
#         return None

class PersonInChargeListSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.company_name', read_only=True)

    class Meta:
        model = PersonInCharge
        fields = ['person_in_charge_id', 'company_name', 'name', 'position', 'email',
                  'mobile_number', 'landline_number']


class CreatePersonInChargeSerializer(serializers.ModelSerializer):

    class Meta:
        model = PersonInCharge
        fields = ['name', 'position', 'email', 'mobile_number', 'landline_number']

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user

        if not hasattr(user, 'company'):
            raise serializers.ValidationError({'error': 'Authenticated user is not a company.'})

        company = user.company
        return PersonInCharge.objects.create(company=company, **validated_data)


class EditPersonInChargeSerializer(serializers.ModelSerializer):
    company_id = serializers.PrimaryKeyRelatedField(source='company', queryset=Company.objects.all(), required=True)

    class Meta:
        model = PersonInCharge
        fields = ['company_id', 'name', 'position', 'email',
                  'mobile_number', 'landline_number']


class BulkDeletePersonInChargeSerializer(serializers.Serializer):
    pic_ids = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False,
        write_only=True
    )

    def validate_pic_ids(self, value):
        existing_ids = (PersonInCharge.objects.filter(person_in_charge_id__in=value).
                        values_list('person_in_charge_id', flat=True))

        missing_ids = set(value) - set(str(uuid) for uuid in existing_ids)
        if missing_ids:
            raise serializers.ValidationError(f"The following IDs do not exist: {list(missing_ids)}")
        return value


class InternshipPostingListSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.company_name')
    person_in_charge_name = serializers.CharField(source='person_in_charge.name')
    required_hard_skills = serializers.SerializerMethodField()
    required_soft_skills = serializers.SerializerMethodField()
    key_tasks = serializers.SerializerMethodField()
    min_qualifications = serializers.SerializerMethodField()
    benefits = serializers.SerializerMethodField()

    class Meta:
        model = InternshipPosting
        fields = [
            'internship_posting_id',
            'internship_position',
            'address',
            'other_requirements',
            'is_paid_internship',
            'is_only_for_practicum',
            'internship_date_start',
            'ojt_hours',
            'application_deadline',
            'date_created',
            'date_modified',
            'status',
            'modality',
            'company_name',
            'person_in_charge',
            'person_in_charge_name',
            'required_hard_skills',
            'required_soft_skills',
            'key_tasks',
            'min_qualifications',
            'benefits'
        ]

    def get_required_hard_skills(self, obj):
        return [
            {"id": skill.lightcast_identifier, "name": skill.name}
            for skill in obj.required_hard_skills.all()
        ]

    def get_required_soft_skills(self, obj):
        return [
            {"id": skill.lightcast_identifier, "name": skill.name}
            for skill in obj.required_soft_skills.all()
        ]

    def get_key_tasks(self, obj):
        return [
            {
             "id": key_task.key_task_id,
             "key_task": key_task.key_task
            }
            for key_task in obj.key_tasks.all()
        ]

    def get_min_qualifications(self, obj):
        return [
            {
                "id": min_qualification.min_qualification_id,
                "min_qualification": min_qualification.min_qualification
            }
            for min_qualification in obj.min_qualifications.all()
        ]

    def get_benefits(self, obj):
        return [
            {
                "id": benefit.benefit_id,
                "benefit": benefit.benefit
            }
            for benefit in obj.benefits.all()
        ]


class CreateInternshipPostingSerializer(serializers.ModelSerializer):
    key_tasks = serializers.CharField()
    min_qualifications = serializers.CharField()
    benefits = serializers.CharField()
    required_hard_skills = serializers.CharField()
    required_soft_skills = serializers.CharField()

    class Meta:
        model = InternshipPosting
        fields = ['internship_position', 'address', 'modality', 'internship_date_start', 'ojt_hours',
                  'application_deadline', 'person_in_charge', 'other_requirements',
                  'key_tasks', 'min_qualifications', 'benefits',
                  'required_hard_skills', 'required_soft_skills',
                  'is_paid_internship', 'is_only_for_practicum', 'status'
        ]

    def validate(self, attrs):
        errors = []

        address = attrs.get('address')
        if len(address) < 15:
            raise serializers.ValidationError({'address': 'Address must be at least 15 characters.'})

        coordinates = get_coordinates(address)
        if coordinates:
            lat, lng = coordinates
            attrs['coordinates'] = {'lat': lat, 'lng': lng}
        else:
            raise serializers.ValidationError({'address': 'Unable to retrieve coordinates.'})

        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        company = getattr(user, 'company', None)

        if not company:
            raise serializers.ValidationError({'error': 'Authenticated user is not a company.'})

        key_tasks_json = validated_data.pop('key_tasks')
        min_qualifications_json = validated_data.pop('min_qualifications')
        benefits_json = validated_data.pop('benefits')
        required_hard_skills_json = validated_data.pop('required_hard_skills')
        required_soft_skills_json = validated_data.pop('required_soft_skills')
        coordinates = validated_data.pop('coordinates', None)

        internship_posting = InternshipPosting.objects.create(company=company, **validated_data)

        if coordinates:
            internship_posting.latitude = coordinates['lat']
            internship_posting.longitude = coordinates['lng']
            internship_posting.save()

        if key_tasks_json:
            try:
                if isinstance(key_tasks_json, str):
                    key_tasks_json = json.loads(key_tasks_json)

                key_tasks = []
                for task_json in key_tasks_json:
                    if len(task_json['key_task']) > 255:
                        raise serializers.ValidationError(
                            {"key_tasks": "Each key task must be at most 255 characters."})

                    task_instance = KeyTask.objects.create(
                        internship_posting=internship_posting,
                        key_task=task_json['key_task']
                    )
                    key_tasks.append(task_instance)

                internship_posting.key_tasks.set(key_tasks)

            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid format for key_tasks")
            except TypeError:
                raise serializers.ValidationError("The provided key_tasks format is not correct.")

        if min_qualifications_json:
            try:
                if isinstance(min_qualifications_json, str):
                    min_qualifications_json = json.loads(min_qualifications_json)

                min_qualifications = []
                for qualification_json in min_qualifications_json:
                    if len(qualification_json['min_qualification']) > 255:
                        raise serializers.ValidationError(
                            {"min_qualifications": "Each qualification must be at most 255 characters."})

                    qualification_instance = MinQualification.objects.create(
                        internship_posting=internship_posting,
                        min_qualification=qualification_json['min_qualification']
                    )
                    min_qualifications.append(qualification_instance)

                internship_posting.min_qualifications.set(min_qualifications)

            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid format for min_qualifications")
            except TypeError:
                raise serializers.ValidationError("The provided min_qualifications format is not correct.")

        if benefits_json:
            try:
                if isinstance(benefits_json, str):
                    benefits_json = json.loads(benefits_json)

                benefits = []
                for benefit_json in benefits_json:
                    if len(benefit_json['benefit']) > 255:
                        raise serializers.ValidationError({"benefits": "Each benefit must be at most 255 characters."})

                    benefit_instance = Benefit.objects.create(
                        internship_posting=internship_posting,
                        benefit=benefit_json['benefit']
                    )
                    benefits.append(benefit_instance)

                internship_posting.benefits.set(benefits)

            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid format for benefits")
            except TypeError:
                raise serializers.ValidationError("The provided benefits format is not correct.")

        if required_hard_skills_json:
            try:
                hard_skills_json = json.loads(required_hard_skills_json)
                hard_skills = []
                for skill in hard_skills_json:
                    skill_instance, _ = HardSkillsTagList.objects.get_or_create(
                        lightcast_identifier=skill['id'],
                        defaults={'name': skill['name']}
                    )
                    hard_skills.append(skill_instance)
                internship_posting.required_hard_skills.set(hard_skills)
            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid format for required_hard_skills")

        if required_soft_skills_json:
            try:
                soft_skills_json = json.loads(required_soft_skills_json)
                soft_skills = []
                for skill in soft_skills_json:
                    skill_instance, _ = SoftSkillsTagList.objects.get_or_create(
                        lightcast_identifier=skill['id'],
                        defaults={'name': skill['name']}
                    )
                    soft_skills.append(skill_instance)
                internship_posting.required_soft_skills.set(soft_skills)
            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid format for required_soft_skills")

        return internship_posting


class EditInternshipPostingSerializer(serializers.ModelSerializer):
    key_tasks = serializers.CharField()
    min_qualifications = serializers.CharField()
    benefits = serializers.CharField()
    required_hard_skills = serializers.CharField()
    required_soft_skills = serializers.CharField()
    displayed_required_hard_skills = serializers.SerializerMethodField()
    displayed_required_soft_skills = serializers.SerializerMethodField()

    class Meta:
        model = InternshipPosting
        fields = ['internship_position', 'address', 'modality', 'internship_date_start', 'ojt_hours',
                  'application_deadline', 'person_in_charge', 'other_requirements',
                  'key_tasks', 'min_qualifications', 'benefits',
                  'required_hard_skills', 'required_soft_skills',
                  'displayed_required_hard_skills', 'displayed_required_soft_skills',
                  'is_paid_internship', 'is_only_for_practicum', 'status'
        ]

    def get_displayed_required_hard_skills(self, obj):
        return [
            {"id": skill.lightcast_identifier, "name": skill.name}
            for skill in obj.required_hard_skills.all()
        ]

    def get_displayed_required_soft_skills(self, obj):
        return [
            {"id": skill.lightcast_identifier, "name": skill.name}
            for skill in obj.required_soft_skills.all()
        ]

    def validate(self, attrs):
        address = attrs.get('address')
        if address and len(address) < 15:
            raise serializers.ValidationError({'address': 'Address must be at least 15 characters.'})

        coordinates = get_coordinates(address)
        if coordinates:
            lat, lng = coordinates
            attrs['coordinates'] = {'lat': lat, 'lng': lng}
        else:
            raise serializers.ValidationError({'address': 'Unable to retrieve coordinates.'})

        return attrs

    def update(self, instance, validated_data):

        key_tasks_json = validated_data.pop('key_tasks', [])
        min_qualifications_json = validated_data.pop('min_qualifications', [])
        benefits_json = validated_data.pop('benefits', [])
        required_hard_skills_json = validated_data.pop('required_hard_skills', None)
        required_soft_skills_json = validated_data.pop('required_soft_skills', None)
        coordinates = validated_data.pop('coordinates', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if coordinates:
            instance.latitude = coordinates['lat']
            instance.longitude = coordinates['lng']

        instance.save()

        if key_tasks_json:
            try:
                instance.key_tasks.all().delete()

                if isinstance(key_tasks_json, str):
                    key_tasks_json = json.loads(key_tasks_json)

                key_tasks = []
                for task_json in key_tasks_json:
                    if len(task_json['key_task']) > 255:
                        raise serializers.ValidationError(
                            {"key_tasks": "Each key task must be at most 255 characters."})

                    task_instance = KeyTask.objects.create(
                        internship_posting=instance,
                        key_task=task_json['key_task']
                    )
                    key_tasks.append(task_instance)

                instance.key_tasks.set(key_tasks)

            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid format for key_tasks")
            except TypeError:
                raise serializers.ValidationError("The provided key_tasks format is not correct.")

        if min_qualifications_json:
            try:
                instance.min_qualifications.all().delete()

                if isinstance(min_qualifications_json, str):
                    min_qualifications_json = json.loads(min_qualifications_json)

                min_qualifications = []
                for qualification_json in min_qualifications_json:
                    if len(qualification_json['min_qualification']) > 255:
                        raise serializers.ValidationError(
                            {"min_qualifications": "Each qualification must be at most 255 characters."})

                    qualification_instance = MinQualification.objects.create(
                        internship_posting=instance,
                        min_qualification=qualification_json['min_qualification']
                    )
                    min_qualifications.append(qualification_instance)

                instance.min_qualifications.set(min_qualifications)

            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid format for min_qualifications")
            except TypeError:
                raise serializers.ValidationError("The provided min_qualifications format is not correct.")

        if benefits_json:
            try:
                instance.benefits.all().delete()

                if isinstance(benefits_json, str):
                    benefits_json = json.loads(benefits_json)

                benefits = []
                for benefit_json in benefits_json:
                    if len(benefit_json['benefit']) > 255:
                        raise serializers.ValidationError({"benefits": "Each benefit must be at most 255 characters."})

                    benefit_instance = Benefit.objects.create(
                        internship_posting=instance,
                        benefit=benefit_json['benefit']
                    )
                    benefits.append(benefit_instance)

                instance.benefits.set(benefits)

            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid format for benefits")
            except TypeError:
                raise serializers.ValidationError("The provided benefits format is not correct.")

        if required_hard_skills_json:
            try:
                hard_skills_json = json.loads(required_hard_skills_json)
                hard_skills = []
                for skill in hard_skills_json:
                    skill_instance, _ = HardSkillsTagList.objects.get_or_create(
                        lightcast_identifier=skill['id'],
                        defaults={'name': skill['name']}
                    )
                    hard_skills.append(skill_instance)
                instance.required_hard_skills.set(hard_skills)
            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid format for required_hard_skills")

        if required_soft_skills_json:
            try:
                soft_skills_json = json.loads(required_soft_skills_json)
                soft_skills = []
                for skill in soft_skills_json:
                    skill_instance, _ = SoftSkillsTagList.objects.get_or_create(
                        lightcast_identifier=skill['id'],
                        defaults={'name': skill['name']}
                    )
                    soft_skills.append(skill_instance)
                instance.required_soft_skills.set(soft_skills)
            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid format for required_soft_skills")

        return instance


class BulkDeleteInternshipPostingSerializer(serializers.Serializer):
    posting_ids = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False,
        write_only=True
    )

    def validate_posting_ids(self, value):
        existing_ids = (InternshipPosting.objects.filter(internship_posting_id__in=value).
                        values_list('internship_posting_id', flat=True))

        missing_ids = set(value) - set(str(uuid) for uuid in existing_ids)
        if missing_ids:
            raise serializers.ValidationError(f"The following IDs do not exist: {list(missing_ids)}")
        return value


class ToggleInternshipPostingSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=["Open", "Closed"])

    class Meta:
        model = InternshipPosting
        fields = ['internship_posting_id', 'status']