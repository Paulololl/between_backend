from django.utils.timezone import now

from client_matching.models import InternshipPosting


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
