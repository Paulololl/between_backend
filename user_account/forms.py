from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from datetime import datetime, timedelta
from django.utils.timezone import now


class DateJoinedFilter(admin.SimpleListFilter):
    title = _('date joined')
    parameter_name = 'date_joined'

    def lookups(self, request, model_admin):
        return [
            ('today', _('Today')),
            ('7_days', _('Past 7 days')),
            ('this_month', _('This month')),
            ('this_year', _('This year')),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        now_dt = now()

        if value == 'today':
            start = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            return queryset.filter(user__date_joined__range=(start, end))

        elif value == '7_days':
            start = now_dt - timedelta(days=7)
            return queryset.filter(user__date_joined__gte=start)

        elif value == 'this_month':
            start = now_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
            return queryset.filter(user__date_joined__range=(start, next_month))

        elif value == 'this_year':
            start = now_dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = start.replace(year=start.year + 1)
            return queryset.filter(user__date_joined__range=(start, end))

        return queryset
