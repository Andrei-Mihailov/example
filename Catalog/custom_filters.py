import datetime
import pytz
import json

from django.utils import timezone
from django.contrib.admin import SimpleListFilter
from .models import GroupEvent, Event, Act


class GroupEventFilter(SimpleListFilter):
    title = 'Мероприятие'
    parameter_name = 'event'

    def lookups(self, request, model_admin):
        events = []
        for groupevent in GroupEvent.objects.all():
            events.append((f'{groupevent.title}_{groupevent.sub_title}',
                          f'{groupevent.title}_{groupevent.sub_title}'))

        return events

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        title, subtitle = self.value().split('_')
        if request.path.endswith('event/'):
            return queryset.filter(group__title=title,
                                   group__sub_title=subtitle)
        elif request.path.endswith('act/'):
            return queryset.filter(event__group__title=title,
                                   event__group__sub_title=subtitle)
        else:
            return queryset.filter(act__event__group__title=title,
                                   act__event__group__sub_title=subtitle)


class EventFilter(SimpleListFilter):
    title = 'День'
    parameter_name = 'date'

    def lookups(self, request, model_admin):
        events = []
        for event in Event.objects.all():
            date = timezone.localtime(event.date, timezone=pytz.timezone('Europe/Moscow'))
            events.append((f'{date.strftime("%d.%m.%Y")}',
                          f'{date.strftime("%d.%m.%Y")}'))

        return events

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        date = datetime.datetime.strptime(self.value(), '%d.%m.%Y')
        date = date.astimezone(datetime.timezone.utc)
        return queryset.filter(event__date=date)


class ActFilter(SimpleListFilter):
    title = 'Концерт'
    parameter_name = 'act'

    def lookups(self, request, model_admin):
        acts = []
        for act in Act.objects.all():
            groups = eval(act.groups)
            groups_str = ', '.join(groups)
            acts.append((f'{groups_str}',
                         f'{groups_str}'))
        return acts

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        search_terms = json.dumps(self.value().split(', '), ensure_ascii=False)
        act = Act.objects.filter(groups__contains=search_terms).first()
        return queryset.filter(act=act)
