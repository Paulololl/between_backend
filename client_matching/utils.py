from django.contrib.admin import SimpleListFilter
from django.utils.timezone import now
from sentence_transformers import SentenceTransformer
import numpy as np
from client_matching.models import InternshipPosting

model = SentenceTransformer('all-MiniLM-L6-v2')


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
        weights = np.array([0.4, 0.4, 0.1, 0.1])
    else:
        weights = np.array([0.3, 0.3, 0.05, 0.05, 0.1, 0.1, 0.1])

    def encode_text(text):
        emb = model.encode(text)
        if isinstance(emb, tuple):
            emb = emb[0]
        return np.array(emb)

    if is_applicant:
        hard_skills = extract_skill_names(profile.get("hard_skills", []))
        soft_skills = extract_skill_names(profile.get("soft_skills", []))
        address = profile.get("address", "")
        modality = profile.get("preferred_modality", "")

        hard_skills_emb = encode_text(" ".join(hard_skills))
        soft_skills_emb = encode_text(" ".join(soft_skills))
        address_emb = encode_text(address)
        modality_emb = encode_text(modality)

        embeddings = np.vstack([hard_skills_emb, soft_skills_emb, address_emb, modality_emb])
        weighted_embedding = np.average(embeddings, axis=0, weights=weights)

    else:
        required_hard_skills = extract_skill_names(profile.get("required_hard_skills", []))
        required_soft_skills = extract_skill_names(profile.get("required_soft_skills", []))
        address = profile.get("address", "")
        modality = profile.get("modality", "")
        min_qualification = ", ".join(profile.get("min_qualifications", [])) or ""
        benefit = ", ".join(profile.get("benefits", [])) or ""
        key_task = ", ".join(profile.get("key_tasks", [])) or ""

        hard_skills_emb = encode_text(" ".join(required_hard_skills))
        soft_skills_emb = encode_text(" ".join(required_soft_skills))
        address_emb = encode_text(address)
        modality_emb = encode_text(modality)
        min_qual_emb = encode_text(min_qualification)
        benefit_emb = encode_text(benefit)
        key_task_emb = encode_text(key_task)

        embeddings = np.vstack([
            hard_skills_emb,
            soft_skills_emb,
            address_emb,
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


def cosine_compare(applicant_embedding: np.ndarray, applicant_profile: dict,
                   internship_posting_embedding: np.ndarray, internship_posting_profiles: list):
    applicant_embedding = np.array(applicant_embedding).flatten()

    similarities = []
    for idx, comp_emb in enumerate(internship_posting_embedding):
        comp_emb = np.array(comp_emb).flatten()
        score = cosine_similarity(applicant_embedding, comp_emb)
        similarities.append((score, internship_posting_profiles[idx]))

        # Sort descending by similarity score
    similarities.sort(key=lambda x: x[0], reverse=True)

    ranking_json = []
    for score, profile in similarities:
        ranking_json.append({
            "internship_posting_id": profile["uuid"],
            "similarity_score": round(float(score), 2),
            # "address": profile["address"],
            # "modality": profile["modality"],
            # "min_qualifications": profile.get("min_qualifications", []),
            # "benefits": profile.get("benefits", []),
            # "key_tasks": profile.get("key_tasks", []),
            # "required_hard_skills": profile.get("required_hard_skills", []),
            # "required_soft_skills": profile.get("required_soft_skills", []),
        })

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


