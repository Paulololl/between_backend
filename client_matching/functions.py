from django.db.models import Max

from client_matching.models import InternshipPosting
from client_matching.serializers import InternshipMatchSerializer
import random


def run_internship_matching(applicant):
    latest_modified = InternshipPosting.objects.exclude(status='Deleted') \
        .aggregate(Max('date_modified'))['date_modified__max']

    user_modified = getattr(applicant.user, 'date_modified', None)
    last_matched = applicant.last_matched

    should_run_matching = False

    if latest_modified:
        if last_matched is None:
            should_run_matching = True
        elif latest_modified > last_matched:
            should_run_matching = True

    if user_modified and (last_matched is None or user_modified > last_matched):
        should_run_matching = True

    if should_run_matching:
        serializer = InternshipMatchSerializer(context={'applicant': applicant})
        serializer.create(validated_data={})


def fisher_yates_shuffle(queryset):
    items = list(queryset)
    n = len(items)
    for i in range(n - 1, 0, -1):
        j = random.randint(0, i)
        items[i], items[j] = items[j], items[i]
    return items

