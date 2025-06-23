import logging

from django.core.cache import cache
from django.db.models import Max

from client_matching.models import InternshipPosting
from client_matching.serializers import InternshipMatchSerializer
import random
from django.db.models import Max


logger = logging.getLogger(__name__)


def run_internship_matching(applicant):
    try:
        cache_key = f"matching_in_progress:{applicant.user.user_id}"

        if cache.get(cache_key):
            logger.info(f"[MATCHING SKIP] Matching already in progress for applicant {applicant.user.user_id}")
            return

        last_matched = applicant.last_matched
        user_modified = getattr(applicant.user, 'date_modified', None)
        latest_modified = InternshipPosting.objects.exclude(status='Deleted') \
            .aggregate(Max('date_modified'))['date_modified__max']

        should_run_matching = False

        if latest_modified and (last_matched is None or latest_modified > last_matched):
            should_run_matching = True
        if user_modified and (last_matched is None or user_modified > last_matched):
            should_run_matching = True

        if not should_run_matching:
            logger.info(f"[MATCHING SKIP] Applicant {applicant.user.user_id} has no significant changes.")
            return

        logger.info(f"[MATCHING START] Running matching for applicant {applicant.user.user_id}")
        cache.set(cache_key, True, timeout=300)

        try:
            serializer = InternshipMatchSerializer(context={'applicant': applicant})
            serializer.create(validated_data={})
            logger.info(f"[MATCHING COMPLETE] Matching complete for applicant {applicant.user.user_id}")
        except Exception as e:
            logger.error(f"[MATCHING ERROR] Matching failed for applicant {applicant.user.user_id}: {e}")
            raise
        finally:
            cache.delete(cache_key)

    except Exception as e:
        logger.error(f"[MATCHING SYSTEM ERROR] Failed to execute matching logic: {e}")


def fisher_yates_shuffle(queryset):
    items = list(queryset)
    n = len(items)
    for i in range(n - 1, 0, -1):
        j = random.randint(0, i)
        items[i], items[j] = items[j], items[i]
    return items
