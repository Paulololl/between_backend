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

SIMILARITY_THRESHOLD = 0.73  # 0.73

SIMILARITY_WEIGHT = 0.95
MODALITY_WEIGHT = 0.02
DISTANCE_WEIGHT = 0.03

EMBEDDING_CACHE_TIMEOUT = 3600
EMBEDDING_DIMENSION = 384

# Old weights with location / address included in embedding
# APPLICANT_WEIGHTS = np.array([0.35, 0.35, 0.1, 0.1, 0.1])
# POSTING_WEIGHTS = np.array([0.3, 0.3, 0.05, 0.05, 0.1, 0.1, 0.1])

APPLICANT_WEIGHTS = np.array([0.50, 0.25, 0.25])
POSTING_WEIGHTS = np.array([0.50, 0.10, 0.20, 0.20])


@lru_cache(maxsize=1)
def get_sentence_model():
    try:
        os.environ["HF_HOME"] = "/tmp/huggingface"
        os.makedirs(os.environ["HF_HOME"], exist_ok=True)

        model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        model._first_module().auto_model = torch.quantization.quantize_dynamic(
            model._first_module().auto_model, {torch.nn.Linear}, dtype=torch.qint8
        )
        logger.info("Sentence transformer model loaded with quantization")
        return model
    except Exception as e:
        logger.error(f"Failed to load sentence transformer model: {e}")
        raise


def generate_embedding_cache_key(text: str) -> str:
    return f"text_embedding:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def encode_text_with_cache(text: str) -> np.ndarray:
    if not text or not text.strip():
        return np.zeros(EMBEDDING_DIMENSION, dtype=np.float32)

    cache_key = generate_embedding_cache_key(text)
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


def embed_each_item(item_list: List[str]) -> np.ndarray:
    if not item_list:
        return np.zeros(EMBEDDING_DIMENSION, dtype=np.float32)

    embeddings = []
    for item in item_list:
        if item and isinstance(item, str) and item.strip():
            embeddings.append(encode_text_with_cache(item.strip()))
    return np.mean(embeddings, axis=0) if embeddings else np.zeros(EMBEDDING_DIMENSION, dtype=np.float32)


# def embed_each_item(item_list: List[str]) -> np.ndarray:
#     if not item_list:
#         return np.zeros(EMBEDDING_DIMENSION, dtype=np.float32)
#
#     filtered_items = [item.strip() for item in item_list if item and isinstance(item, str) and item.strip()]
#     if not filtered_items:
#         return np.zeros(EMBEDDING_DIMENSION, dtype=np.float32)
#
#     embeddings: List[Optional[np.ndarray]] = [None] * len(filtered_items)
#     uncached_texts = []
#     uncached_indices = []
#
#     for idx, text in enumerate(filtered_items):
#         cache_key = generate_embedding_cache_key(text)
#         cached_embedding = cache.get(cache_key)
#         if cached_embedding is not None:
#             embeddings[idx] = np.array(cached_embedding, dtype=np.float32)
#         else:
#             uncached_indices.append(idx)
#             uncached_texts.append(text)
#
#     if uncached_texts:
#         model = get_sentence_model()
#         new_embeddings = model.encode(uncached_texts, convert_to_numpy=True, batch_size=8)
#         for idx, embedding in zip(uncached_indices, new_embeddings):
#             embedding = embedding.astype(np.float32)
#             embeddings[idx] = embedding
#             cache.set(generate_embedding_cache_key(filtered_items[idx]), embedding.tolist(), EMBEDDING_CACHE_TIMEOUT)
#
#     final_embeddings = [emb for emb in embeddings if emb is not None]
#     return np.mean(final_embeddings, axis=0) if final_embeddings else np.zeros(EMBEDDING_DIMENSION, dtype=np.float32)


def extract_skill_names(skills) -> List[str]:
    if not skills:
        return []
    try:
        if hasattr(skills, 'all'):
            return [skill.name for skill in skills.all() if hasattr(skill, 'name') and skill.name]
        elif hasattr(skills, 'values_list'):
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


def get_profile_embedding(profile: dict, is_applicant: bool = True) -> np.ndarray:
    try:
        if is_applicant:
            hard_skills = extract_skill_names(profile.get("hard_skills", []))
            soft_skills = extract_skill_names(profile.get("soft_skills", []))
            intro = profile.get("quick_introduction", "")

            vectors = [
                embed_each_item(hard_skills),
                embed_each_item(soft_skills),
                encode_text_with_cache(intro),
            ]
            weights = APPLICANT_WEIGHTS
        else:
            hard_skills = extract_skill_names(profile.get("required_hard_skills", []))
            soft_skills = extract_skill_names(profile.get("required_soft_skills", []))
            qualifications = profile.get("min_qualifications", [])
            tasks = profile.get("key_tasks", [])

            vectors = [
                embed_each_item(hard_skills),
                embed_each_item(soft_skills),
                embed_each_item(qualifications),
                embed_each_item(tasks),
            ]
            weights = POSTING_WEIGHTS

        return np.average(vectors, axis=0, weights=weights).astype(np.float32)

    except Exception as e:
        logger.error(f"Failed to generate profile embedding: {e}")
        return np.zeros(EMBEDDING_DIMENSION, dtype=np.float32)


def get_posting_embeddings_batch(posting_profiles: List[dict]) -> np.ndarray:
    embeddings = []
    for profile in posting_profiles:
        embedding = get_profile_embedding(profile, is_applicant=False)
        embeddings.append(embedding)
    return np.array(embeddings, dtype=np.float32)


def modality_score(applicant_modality: str, posting_modality: str) -> float:
    if applicant_modality == posting_modality:
        return 1.0
    if "Hybrid" in [applicant_modality, posting_modality]:
        if "Onsite" in [applicant_modality, posting_modality] or "WorkFromHome" in [applicant_modality, posting_modality]:
            return 0.5
    return 0.0


def calculate_distance(coord1: tuple, coord2: tuple) -> float:
    try:
        if None in coord1 or None in coord2:
            return 0.0
        return great_circle(coord1, coord2).km
    except Exception as e:
        logger.warning(f"Distance calculation failed: {e}")
        return 0.0


def cosine_similarity_vectorized(a: np.ndarray, b: np.ndarray) -> Union[float, np.ndarray]:
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
        return 0.0 if b.ndim == 1 else np.zeros(len(b))


def cosine_compare(applicant_embedding: np.ndarray, applicant_profile: dict,
                   posting_embeddings: np.ndarray, posting_profiles: list) -> List[Dict]:
    try:
        similarity_scores = cosine_similarity_vectorized(applicant_embedding, posting_embeddings)
        applicant_coords = (applicant_profile.get("latitude"), applicant_profile.get("longitude"))
        applicant_modality = applicant_profile.get("preferred_modality", "")

        results = []
        for score, profile in zip(similarity_scores, posting_profiles):
            profile_coords = (profile.get("latitude"), profile.get("longitude"))
            posting_modality = profile.get("modality", "")
            is_remote = posting_modality == "WorkFromHome"

            if not is_remote and None not in applicant_coords + profile_coords:
                distance_km = calculate_distance(applicant_coords, profile_coords)
            else:
                distance_km = 0.0

            mod_score = modality_score(applicant_modality, posting_modality)

            if not is_remote and distance_km:
                if distance_km <= 5:
                    distance_score = 1.0
                elif distance_km <= 10:
                    distance_score = 0.75
                elif distance_km <= 15:
                    distance_score = 0.5
                elif distance_km <= 20:
                    distance_score = 0.25
                else:
                    distance_score = 0.0
                dist_component = distance_score * DISTANCE_WEIGHT
            else:
                dist_component = DISTANCE_WEIGHT

            sim_component = score * SIMILARITY_WEIGHT
            mod_component = mod_score * MODALITY_WEIGHT

            final_score = sim_component + mod_component + dist_component

            results.append({
                "internship_posting_id": profile.get("uuid", "Unknown UUID"),
                "similarity_score": round(final_score, 3),
                "semantic_similarity_component": round(sim_component, 3),
                "modality_score_component": round(mod_component, 3),
                "distance_score_component": round(dist_component, 3),
                "raw_cosine_similarity": round(score, 3),
                "modality": profile.get("modality", ""),
                "distance_km": round(distance_km, 2) if not is_remote else "Remote / Unknown",
            })

        return sorted(results, key=lambda x: x["similarity_score"], reverse=True)

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


