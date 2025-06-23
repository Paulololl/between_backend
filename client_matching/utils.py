import hashlib
import json
import logging
from datetime import timedelta
from functools import lru_cache
from typing import List, Optional, Tuple, Union, Dict

import torch
from django.contrib.admin import SimpleListFilter
from django.core.cache import cache
from django.utils.timezone import now
from geopy.distance import great_circle
from sentence_transformers import SentenceTransformer
import numpy as np
from client_matching.models import InternshipPosting, InternshipRecommendation
from user_account.models import Applicant
import os

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.20
SIMILARITY_WEIGHT = 0.95
DISTANCE_WEIGHT = 0.05
EMBEDDING_CACHE_TIMEOUT = 3600
EMBEDDING_DIMENSION = 384

APPLICANT_WEIGHTS = np.array([0.35, 0.35, 0.1, 0.1, 0.1])
POSTING_WEIGHTS = np.array([0.3, 0.3, 0.05, 0.05, 0.1, 0.1, 0.1])


@lru_cache(maxsize=1)
def get_sentence_model():
    try:
        os.environ["HF_HOME"] = "/tmp/huggingface"
        os.makedirs(os.environ["HF_HOME"], exist_ok=True)

        # model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        model = SentenceTransformer('sentence-transformers/paraphrase-MiniLM-L3-v2')
        model._first_module().auto_model = torch.quantization.quantize_dynamic(
            model._first_module().auto_model, {torch.nn.Linear}, dtype=torch.qint8
        )
        logger.info("Sentence transformer model loaded with quantization")
        return model
    except Exception as e:
        logger.error(f"Failed to load sentence transformer model: {e}")
        raise


def generate_embedding_cache_key(profile_data: str, is_applicant: bool = True) -> str:
    """Generate cache key for embeddings"""
    profile_hash = hashlib.md5(profile_data.encode()).hexdigest()
    prefix = "applicant" if is_applicant else "posting"
    return f"embedding:{prefix}:{profile_hash}"


def extract_skill_names(skills) -> List[str]:
    """Extract skill names from Django QuerySet or list with validation"""
    if not skills:
        return []

    try:
        if hasattr(skills, 'all'):
            # Django QuerySet
            return [skill.name for skill in skills.all() if hasattr(skill, 'name') and skill.name]
        elif hasattr(skills, 'values_list'):
            # Already a QuerySet, get names directly
            return list(skills.values_list('name', flat=True).filter(name__isnull=False))
        elif isinstance(skills, list):
            result = []
            for skill in skills:
                if isinstance(skill, dict):
                    name = skill.get("name", "").strip()
                    if name:
                        result.append(name)
                elif isinstance(skill, str) and skill.strip():
                    result.append(skill.strip())
                elif hasattr(skill, 'name') and skill.name:
                    result.append(str(skill.name))
            return result
    except Exception as e:
        logger.warning(f"Error extracting skill names: {e}")

    return []


def validate_coordinates(latitude: Optional[float], longitude: Optional[float]) -> Tuple[
    bool, Optional[float], Optional[float]]:
    if latitude is None or longitude is None:
        return False, None, None

    try:
        lat = float(latitude)
        lon = float(longitude)

        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return True, lat, lon
    except (ValueError, TypeError):
        pass

    logger.warning(f"Invalid coordinates: lat={latitude}, lon={longitude}")
    return False, None, None


def encode_text_with_cache(text: str) -> np.ndarray:
    if not text or not text.strip():
        return np.zeros(EMBEDDING_DIMENSION, dtype=np.float32)

    cache_key = f"text_embedding:{hashlib.md5(text.encode()).hexdigest()}"
    cached_embedding = cache.get(cache_key)

    if cached_embedding is not None:
        return np.array(cached_embedding, dtype=np.float32)

    try:
        model = get_sentence_model()
        embedding = model.encode(text, convert_to_numpy=True).astype(np.float32)

        cache.set(cache_key, embedding.tolist(), EMBEDDING_CACHE_TIMEOUT)
        return embedding
    except Exception as e:
        logger.error(f"Failed to encode text: {e}")
        return np.zeros(EMBEDDING_DIMENSION, dtype=np.float32)


def batch_encode_with_cache(texts: List[str]) -> List[np.ndarray]:
    results = []
    texts_to_encode = []
    indexes_to_encode = []

    for i, text in enumerate(texts):
        cache_key = f"text_embedding:{hashlib.md5(text.encode()).hexdigest()}"
        cached = cache.get(cache_key)
        if cached:
            results.append(np.array(cached, dtype=np.float32))
        else:
            results.append(None)
            texts_to_encode.append(text)
            indexes_to_encode.append(i)

    if texts_to_encode:
        model = get_sentence_model()
        encodings = model.encode(texts_to_encode, convert_to_numpy=True).astype(np.float32)
        for idx, encoding in zip(indexes_to_encode, encodings):
            results[idx] = encoding
            cache.set(
                f"text_embedding:{hashlib.md5(texts[idx].encode()).hexdigest()}",
                encoding.tolist(),
                EMBEDDING_CACHE_TIMEOUT
            )

    return results


def get_profile_embedding(profile: dict, is_applicant: bool = True) -> np.ndarray:
    profile_str = json.dumps(profile, sort_keys=True, default=str)
    cache_key = generate_embedding_cache_key(profile_str, is_applicant)

    cached_embedding = cache.get(cache_key)
    if cached_embedding is not None:
        return np.array(cached_embedding, dtype=np.float32)

    try:
        if is_applicant:
            hard_skills = extract_skill_names(profile.get("hard_skills", []))
            soft_skills = extract_skill_names(profile.get("soft_skills", []))
            modality = str(profile.get("preferred_modality", "")).strip()
            quick_introduction = str(profile.get("quick_introduction", "")).strip()
            latitude = profile.get("latitude")
            longitude = profile.get("longitude")

            is_valid_coords, lat, lon = validate_coordinates(latitude, longitude)
            location_text = f"{lat} {lon}" if is_valid_coords else None

            texts = [
                str(" ".join(hard_skills) or ""),
                str(" ".join(soft_skills) or ""),
                str(location_text or ""),
                str(modality or ""),
                str(quick_introduction or "")
            ]
            embeddings = batch_encode_with_cache(texts)
            weights = APPLICANT_WEIGHTS

        else:
            required_hard_skills = extract_skill_names(profile.get("required_hard_skills", []))
            required_soft_skills = extract_skill_names(profile.get("required_soft_skills", []))
            modality = str(profile.get("modality", "")).strip()
            min_qualification = ", ".join(profile.get("min_qualifications", [])) or ""
            benefit = ", ".join(profile.get("benefits", [])) or ""
            key_task = ", ".join(profile.get("key_tasks", [])) or ""
            latitude = profile.get("latitude")
            longitude = profile.get("longitude")

            is_valid_coords, lat, lon = validate_coordinates(latitude, longitude)
            location_text = f"{lat} {lon}" if is_valid_coords else None

            texts = [
                str(" ".join(required_hard_skills) or ""),
                str(" ".join(required_soft_skills) or ""),
                str(location_text or ""),
                str(modality or ""),
                str(min_qualification or ""),
                str(benefit or ""),
                str(key_task or "")
            ]
            embeddings = batch_encode_with_cache(texts)
            weights = POSTING_WEIGHTS

        embeddings = [e if e is not None else np.zeros(EMBEDDING_DIMENSION, dtype=np.float32) for e in embeddings]

        weighted_embedding = np.average(embeddings, axis=0, weights=weights)

        cache.set(cache_key, weighted_embedding.tolist(), EMBEDDING_CACHE_TIMEOUT)
        return weighted_embedding.astype(np.float32)

    except Exception as e:
        logger.error(f"Failed to generate profile embedding: {e}")
        return np.zeros(EMBEDDING_DIMENSION, dtype=np.float32)


def get_posting_embeddings_batch(posting_profiles: List[Dict]) -> Optional[np.ndarray]:
    if not posting_profiles:
        return None

    embeddings = []
    for profile in posting_profiles:
        try:
            emb = get_profile_embedding(profile, is_applicant=False)
            embeddings.append(emb)
        except Exception as e:
            logger.warning(f"Failed to embed posting profile: {e}")
            embeddings.append(np.zeros(EMBEDDING_DIMENSION, dtype=np.float32))

    return np.vstack(embeddings) if embeddings else None


def cosine_similarity_vectorized(a: np.ndarray, b: np.ndarray) -> Union[float, np.ndarray]:
    """Vectorized cosine similarity calculation"""
    try:
        a_norm = a / np.linalg.norm(a)

        if b.ndim == 1:
            b_norm = b / np.linalg.norm(b)
            return np.dot(a_norm, b_norm)
        else:
            b_norm = b / np.linalg.norm(b, axis=1, keepdims=True)
            return np.dot(b_norm, a_norm)
    except Exception as e:
        logger.error(f"Cosine similarity calculation failed: {e}")
        if b.ndim == 1:
            return 0.0
        else:
            return np.zeros(len(b))


def calculate_distance(coord1: tuple, coord2: tuple) -> float:
    """Calculate distance with error handling"""
    try:
        if None in coord1 or None in coord2:
            return 0.0
        return great_circle(coord1, coord2).km
    except Exception as e:
        logger.warning(f"Distance calculation failed: {e}")
        return 0.0


def cosine_compare(applicant_embedding: np.ndarray, applicant_profile: dict,
                   internship_posting_embedding: np.ndarray, internship_posting_profiles: list) -> List[Dict]:
    """
    Optimized comparison with vectorized operations and Django integration
    """
    if internship_posting_embedding is None or len(internship_posting_embedding) == 0:
        return []

    try:
        applicant_embedding = np.array(applicant_embedding, dtype=np.float32).flatten()

        # Ensure posting embeddings are properly shaped
        if internship_posting_embedding.ndim == 1:
            internship_posting_embedding = internship_posting_embedding.reshape(1, -1)

        # Vectorized similarity calculation
        similarity_scores = cosine_similarity_vectorized(applicant_embedding, internship_posting_embedding)
        if isinstance(similarity_scores, float):
            similarity_scores = np.array([similarity_scores])

        applicant_coords = (applicant_profile.get("latitude"), applicant_profile.get("longitude"))

        # Calculate distances and determine distance consideration
        similarities = []
        distances = []

        for idx, (score, profile) in enumerate(zip(similarity_scores, internship_posting_profiles)):
            profile_coords = (profile.get("latitude"), profile.get("longitude"))
            modality = profile.get("modality", "")

            if modality == "WorkFromHome" or None in applicant_coords or None in profile_coords:
                consider_distance = False
                distance_km = 0.0
            else:
                consider_distance = True
                distance_km = calculate_distance(applicant_coords, profile_coords)

            similarities.append((float(score), distance_km, consider_distance, profile))
            if consider_distance:
                distances.append(distance_km)

        # Calculate final scores
        max_distance = max(distances) if distances else 1.0
        ranking_json = []

        for score, distance_km, consider_distance, profile in similarities:
            if consider_distance and max_distance > 0:
                norm_distance_score = 1 - (distance_km / max_distance)
                final_score = SIMILARITY_WEIGHT * score + DISTANCE_WEIGHT * norm_distance_score
            else:
                final_score = score

            ranking_json.append({
                "internship_posting_id": profile["uuid"],
                "similarity_score": round(final_score, 3),
                "address_distance_km": round(distance_km, 2) if consider_distance else "Remote / Unknown",
                "consider_distance": consider_distance,
                "modality": profile.get("modality", ""),
            })

        # Sort by similarity score descending
        ranking_json.sort(key=lambda x: x["similarity_score"], reverse=True)
        return ranking_json

    except Exception as e:
        logger.error(f"Comparison failed: {e}")
        return []


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
#
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


def monitor_performance(func_name: str):
    """Decorator to monitor function performance in Django"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.info(f"{func_name} executed in {execution_time:.3f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"{func_name} failed after {execution_time:.3f}s: {e}")
                raise
        return wrapper
    return decorator
