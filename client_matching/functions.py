from django.db.models import Max

from client_matching.models import InternshipPosting
from client_matching.serializers import InternshipMatchSerializer
import random


def run_internship_matching(applicant):
    latest_modified = InternshipPosting.objects.exclude(status='Deleted') \
        .aggregate(Max('date_modified'))['date_modified__max']

    if (latest_modified and
        not applicant.last_matched or
        latest_modified > applicant.last_matched or
        applicant.user.date_modified and applicant.user.date_modified > applicant.last_matched
    ):
        serializer = InternshipMatchSerializer(context={'applicant': applicant})
        serializer.create(validated_data={})


def fisher_yates_shuffle(queryset):
    items = list(queryset)
    n = len(items)
    for i in range(n - 1, 0, -1):
        j = random.randint(0, i)
        items[i], items[j] = items[j], items[i]
    return items

