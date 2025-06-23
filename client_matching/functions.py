import logging

from django.core.cache import cache
from django.db.models import Max

from client_matching.models import InternshipPosting
from client_matching.serializers import InternshipMatchSerializer
import random


logger = logging.getLogger(__name__)


def run_internship_matching(applicant):
    """
    Efficient and safe trigger for internship matching:
    - Avoids unnecessary runs if applicant or postings haven't changed
    - Locks matching per applicant using Django cache
    """
    try:
        # Check for 5-minute cache lock
        cache_key = f"matching_in_progress:{applicant.id}"
        if cache.get(cache_key):
            logger.info(f"[MATCHING SKIP] Matching already in progress for applicant {applicant.id}")
            return

        last_matched = applicant.last_matched
        user_modified = getattr(applicant.user, 'date_modified', None)

        latest_modified = InternshipPosting.objects.exclude(status='Deleted') \
            .aggregate(Max('date_modified'))['date_modified__max']

        should_run_matching = False

        if latest_modified and (not last_matched or latest_modified > last_matched):
            should_run_matching = True
        if user_modified and (not last_matched or user_modified > last_matched):
            should_run_matching = True

        if not should_run_matching:
            logger.info(f"[MATCHING SKIP] Applicant {applicant.id} has no significant changes.")
            return

        # Set cache lock for 5 minutes
        cache.set(cache_key, True, timeout=300)

        try:
            logger.info(f"[MATCHING START] Running matching for applicant {applicant.id}")
            serializer = InternshipMatchSerializer(context={'applicant': applicant})
            serializer.create(validated_data={})
            logger.info(f"[MATCHING COMPLETE] Matching complete for applicant {applicant.id}")
        except Exception as e:
            logger.error(f"[MATCHING ERROR] Matching failed for applicant {applicant.id}: {e}")
            raise
        finally:
            # Ensure cache lock is cleared even if failure occurs
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

