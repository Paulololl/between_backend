from datetime import timedelta
from functools import lru_cache

from django.contrib.admin import SimpleListFilter
from django.utils.timezone import now
from geopy.distance import great_circle
from sentence_transformers import SentenceTransformer
import numpy as np
from client_matching.models import InternshipPosting, InternshipRecommendation
from user_account.models import Applicant
import os


@lru_cache(maxsize=1)
def get_sentence_model():
    os.environ["HF_HOME"] = "/tmp/huggingface"
    os.makedirs(os.environ["HF_HOME"], exist_ok=True)
    return SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')


def get_profile_embedding(profile: dict, is_applicant: bool = True):
    def extract_skill_names(skills):
        if hasattr(skills, 'all'):
            return [skill.name for skill in skills.all()]
        elif isinstance(skills, list):
            result = []
            for skill in skills:
                if isinstance(skill, dict):
                    result.append(skill.get("name", ""))
                elif isinstance(skill, str):
                    result.append(skill)
                else:
                    result.append(str(skill))
            return result
        else:
            return []

    # label for each weight
    if is_applicant:
        weights = np.array([0.35, 0.35, 0.1, 0.1, 0.1])
    else:
        weights = np.array([0.3, 0.3, 0.05, 0.05, 0.1, 0.1, 0.1])

    def encode_text(text):
        model = get_sentence_model()
        emb = model.encode(text)
        if isinstance(emb, tuple):
            emb = emb[0]
        return np.array(emb)

    if is_applicant:
        hard_skills = extract_skill_names(profile.get("hard_skills", []))
        soft_skills = extract_skill_names(profile.get("soft_skills", []))
        modality = profile.get("preferred_modality", "")
        quick_introduction = profile.get("quick_introduction", "")
        latitude = profile.get("latitude")
        longitude = profile.get("longitude")

        hard_skills_emb = encode_text(" ".join(hard_skills))
        soft_skills_emb = encode_text(" ".join(soft_skills))
        modality_emb = encode_text(modality)
        quick_introduction_emb = encode_text(quick_introduction)

        if latitude is not None and longitude is not None:
            location_emb = encode_text(f"{latitude} {longitude}")
        else:
            location_emb = np.zeros(384)

        embeddings = np.vstack(
            [
                hard_skills_emb,
                soft_skills_emb,
                location_emb,
                modality_emb,
                quick_introduction_emb
            ]
        )
        weighted_embedding = np.average(embeddings, axis=0, weights=weights)

    else:
        required_hard_skills = extract_skill_names(profile.get("required_hard_skills", []))
        required_soft_skills = extract_skill_names(profile.get("required_soft_skills", []))
        modality = profile.get("modality", "")
        min_qualification = ", ".join(profile.get("min_qualifications", [])) or ""
        benefit = ", ".join(profile.get("benefits", [])) or ""
        key_task = ", ".join(profile.get("key_tasks", [])) or ""
        latitude = profile.get("latitude")
        longitude = profile.get("longitude")

        hard_skills_emb = encode_text(" ".join(required_hard_skills))
        soft_skills_emb = encode_text(" ".join(required_soft_skills))
        modality_emb = encode_text(modality)
        min_qual_emb = encode_text(min_qualification)
        benefit_emb = encode_text(benefit)
        key_task_emb = encode_text(key_task)

        if latitude is not None and longitude is not None:
            location_emb = encode_text(f"{latitude} {longitude}")
        else:
            location_emb = np.zeros(384)

        embeddings = np.vstack([
            hard_skills_emb,
            soft_skills_emb,
            location_emb,
            modality_emb,
            min_qual_emb,
            benefit_emb,
            key_task_emb
        ])
        weighted_embedding = np.average(embeddings, axis=0, weights=weights)

    return weighted_embedding


def cosine_similarity(a: np.ndarray, b: np.ndarray):
    a_norm = a / np.linalg.norm(a)
    b_norm = b / np.linalg.norm(b)
    return np.dot(a_norm, b_norm)


def calculate_distance(coord1: tuple, coord2: tuple) -> float:
    return great_circle(coord1, coord2).km


def cosine_compare(applicant_embedding: np.ndarray, applicant_profile: dict,
                   internship_posting_embedding: np.ndarray, internship_posting_profiles: list):
    if internship_posting_embedding is None or len(internship_posting_embedding) == 0:
        return []

    applicant_embedding = np.array(applicant_embedding).flatten()

    SIMILARITY_WEIGHT = 0.95
    DISTANCE_WEIGHT = 0.05

    applicant_coords = (applicant_profile.get("latitude"), applicant_profile.get("longitude"))
    similarities = []
    distances = []

    for idx, comp_emb in enumerate(internship_posting_embedding):
        comp_emb = np.array(comp_emb).flatten()
        score = cosine_similarity(applicant_embedding, comp_emb)

        profile = internship_posting_profiles[idx]
        profile_coords = (profile.get("latitude"), profile.get("longitude"))
        modality = profile.get("modality", "")

        if modality == "WorkFromHome" or None in applicant_coords or None in profile_coords:
            consider_distance = False
            distance_km = 0.0
        else:
            consider_distance = True
            distance_km = calculate_distance(applicant_coords, profile_coords) or 0.0

        similarities.append((score, distance_km, consider_distance, internship_posting_profiles[idx]))
        distances.append(distance_km if consider_distance else 0.0)

    max_distance = max(distances) or 1
    ranking_json = []

    # # Sort descending by similarity score
    # similarities.sort(key=lambda x: x[0], reverse=True)

    ranking_json = []

    for score, distance_km, consider_distance, profile in similarities:
        if consider_distance:
            norm_distance_score = 1 - (distance_km / max_distance)
            final_score = SIMILARITY_WEIGHT * score + DISTANCE_WEIGHT * norm_distance_score
        else:
            final_score = score
        ranking_json.append({
            "internship_posting_id": profile["uuid"],
            "similarity_score": round(final_score, 2),
            "address_distance_km": round(distance_km, 2) if consider_distance else "Remote / Unknown",
            "consider_distance": consider_distance,
            "modality": profile["modality"],
            # "final_score": round(float(score), 2),
            # "min_qualifications": profile.get("min_qualifications", []),
            # "benefits": profile.get("benefits", []),
            # "key_tasks": profile.get("key_tasks", []),
            # "required_hard_skills": profile.get("required_hard_skills", []),
            # "required_soft_skills": profile.get("required_soft_skills", []),
        })

    ranking_json.sort(key=lambda x: x["similarity_score"], reverse=True)
    return ranking_json


def update_internship_posting_status(company):
    current_time = now()

    InternshipPosting.objects.filter(
        company=company,
        application_deadline__lt=current_time,
        status__in=['Open', 'Closed']
    ).update(status='Expired')

    InternshipPosting.objects.filter(
        company=company,
        application_deadline__gte=current_time,
        status='Expired'
    ).update(status='Open')


def delete_old_deleted_postings():
    threshold = now() - timedelta(days=3)
    InternshipPosting.objects.filter(status='Deleted', date_modified__lt=threshold).delete()


def reset_recommendations_and_tap_count(applicant):
    current_time = now()
    today = current_time.date()
    midnight_today = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    # threshold = now() - timedelta(seconds=20)

    skipped_recommendations = InternshipRecommendation.objects.filter(
        status='Skipped',
        time_stamp__lt=midnight_today,
    )

    skipped_recommendations.update(status='Pending', time_stamp=now())

    if not applicant.tap_count_reset or applicant.tap_count_reset.date() < today:
        applicant.tap_count = 0
        applicant.tap_count_reset = current_time
        applicant.save(update_fields=['tap_count', 'tap_count_reset'])


class InternshipPostingStatusFilter(SimpleListFilter):
    title = 'Internship Posting Status'
    parameter_name = 'posting_status'

    def lookups(self, request, model_admin):
        return [
            ('Open', 'Open'),
            ('Closed', 'Closed'),
            ('Expired', 'Expired'),
            ('Deleted', 'Deleted'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            if self.value() == 'Deleted':
                posting_ids = InternshipPosting.objects.values_list('internship_posting_id', flat=True)
                return queryset.exclude(internship_posting_id__in=posting_ids)
            else:
                posting_ids = InternshipPosting.objects.filter(
                    status=self.value()
                ).values_list('internship_posting_id', flat=True)
                return queryset.filter(internship_posting_id__in=posting_ids)
        return queryset
