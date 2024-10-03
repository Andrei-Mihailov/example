import json
import datetime
import pytz

from django.utils import timezone
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from django.contrib import messages
from django.urls import re_path
from django.http import HttpResponseRedirect
from django.contrib.admin import AdminSite
from django import forms

from . import models
from .utils import format_path, get_or_create_group_event, get_or_create_event, get_or_create_act
from .tasks import import_files, email_users, BATCH_SIZE
from .forms import XForm, ColorsForm
from .custom_filters import GroupEventFilter, EventFilter, ActFilter
from Mydance.config import rus_months, prefix_concerts, client_sync


class MyAdminSite(AdminSite):

    def get_app_list(self, request):
        """
        Return a sorted list of all the installed apps that have been
        registered in this site.
        """
        app_dict = self._build_app_dict(request)

        app_list = sorted(app_dict.values(), key=lambda x: x['name'].lower())

        return app_list


admin.site = MyAdminSite()

admin.site.register(PeriodicTask)
admin.site.register(IntervalSchedule)


class ActsInline(admin.TabularInline):
    model = models.Act

    readonly_fields = (
        'time',
        'display_groups',
        'photo_counter',
        'visible',
        'get_metrics_info',
        'in_trash'
    )
    extra = 0
    show_change_link = True
    exclude = ('groups',)
    verbose_name = "Концерт"
    verbose_name_plural = "Концерты"

    def display_groups(self, obj):
        groups = eval(obj.groups)
        groups_str = ', '.join(groups)
        return mark_safe(groups_str)
    display_groups.short_description = "Студии-школы"

    def get_metrics_info(self, obj: models.Act):
        count = obj.photos.count()
        metrics = obj.photos.count() - obj.photos.filter(metrics=[]).count()
        empty = obj.photos.filter(metrics=[[]]).count()
        return f"{count}/{metrics}/{empty}"
    get_metrics_info.short_description = "Всего фото/обработано/пустые"

    def has_add_permission(self, request, *kwargs):
        return False


class EventsInline(admin.TabularInline):
    model = models.Event

    readonly_fields = (
        'date',
        'get_metrics_info',
        'visible',
        'in_trash'
    )
    extra = 0
    show_change_link = True
    exclude = ('image_url',)
    verbose_name = "День мероприятия"
    verbose_name_plural = "Дни мероприятия"

    def get_metrics_info(self, obj):
        count = 0
        metrics = 0
        empty = 0
        for act in obj.acts.all():
            count += act.photos.count()
            metrics += act.photos.count() - act.photos.filter(metrics=[]).count()
            empty += act.photos.filter(metrics=[[]]).count()
        return f"{count}/{metrics}/{empty}"
    get_metrics_info.short_description = "Всего фото/обработано/пустые"

    def has_add_permission(self, request, *kwargs):
        return False


class ColorsInline(admin.TabularInline):
    model = models.ColorsEvent
    form = ColorsForm
    extra = 0
    verbose_name = "Цвет"
    verbose_name_plural = "Цвета"

    def has_add_permission(self, request, *kwargs):
        return False


class GroupEvent(admin.ModelAdmin):
    fields = [
        'get_image_url',
        ('title', 'sub_title'),
        'get_metrics_info',
        ('price', 'base_sale'),
        ('sale_price_1_limit', 'sale_price_1'),
        ('sale_price_2_limit', 'sale_price_2'),
        ('visible', 'in_trash', 'deleted_at')
    ]
    list_display = (
        'title',
        'sub_title',
        'visible',
        'in_trash',
        'get_metrics_info',
        'get_image_url',
        'deleted_at'
    )
    search_fields = [
        'title',
        'sub_title',
        'get_date',
        'visible'
    ]
    ordering = ('title', 'sub_title')
    readonly_fields = (
        'title',
        'sub_title',
        'get_image_url',
        'in_trash',
        'get_metrics_info',
        'deleted_at',
    )
    exclude = ('image_url',)
    inlines = [ColorsInline,
               EventsInline]
    change_list_template = "admin/model_change_list.html"

    def get_image_url(self, obj):
        return format_html('<img src="/{}" style="max-width: 300px; max-height: 300px;"/>'.format(obj.image_url))
    get_image_url.allow_tags = True
    get_image_url.short_description = "Превью"

    def deleted_at(self, obj):
        pt = PeriodicTask.objects.filter(name=f'Удаление мероприятия {obj.id}')
        if pt.exists():
            return pt.first().start_time
        return '-'
    deleted_at.short_description = 'Дата и время удаления'

    def get_metrics_info(self, obj):
        count = 0
        metrics = 0
        empty = 0
        for event in obj.event.all():
            for act in event.acts.all():
                count += act.photos.count()
                metrics += act.photos.count() - act.photos.filter(metrics=[]).count()
                empty += act.photos.filter(metrics=[[]]).count()
        return f"{count}/{metrics}/{empty}"
    get_metrics_info.short_description = "Всего фото/обработано/пустые"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            re_path('^search/$', self.search_new_folders, name='search_new_folders'),
            re_path('^import/$', self.process_import, name='process_import'),
            re_path('^metrics/$', self.process_metrics, name='process_metrics'),
        ]
        return custom_urls + urls

    def search_new_folders(self, request):
        count_event = 0
        count_acts = 0
        for obj in client_sync.listdir('disk:/'):
            path = obj['path']
            main_path = path.replace('disk:/', '').replace('/' + path.split('/')[-1], '')
            if 'watermark' in main_path:
                continue
            for obj_dates in client_sync.listdir(path):
                path_dates = obj_dates['path']
                for obj_acts in client_sync.listdir(path_dates):
                    path_acts = obj_acts['path']
                    main_path = path_acts.replace('disk:/', '')
                    event_title, event_sub_title, event_date, act_groups, act_time = format_path(main_path)
                    group, _ = get_or_create_group_event(event_title, event_sub_title)
                    event, event_created = get_or_create_event(event_date, group)
                    _, act_created = get_or_create_act(event, act_time, act_groups)
                    if event_created:
                        count_event += 1
                    if act_created:
                        count_acts += 1

        self.message_user(request, f"Добавлено новых папок: мероприятий {count_event}, концертов {count_acts}")
        return HttpResponseRedirect("../")

    def process_import(self, request):
        try:
            for act in models.Act.objects.filter(photo_counter=None):
                time = timezone.localtime(act.time, timezone=pytz.timezone('Europe/Moscow'))
                month = time.month
                month_str = list(rus_months.keys())[month - 1]
                date_str = datetime.datetime.strftime(time.astimezone(
                    pytz.timezone('Europe/Moscow')), "%d") + ' ' + month_str
                if date_str[0] == '0':
                    date_str = date_str[1:]
                time_str = datetime.datetime.strftime(time.astimezone(pytz.timezone('Europe/Moscow')), "%H%M")
                for num in prefix_concerts:
                    path = f"{act.event.group.title}_{act.event.group.sub_title}/{date_str}/{num}_{'_'.join(json.loads(act.groups))}_{time_str}"
                    if client_sync.is_dir(path):
                        import_files.delay(path)
                        photo_count = 0
                        for _ in client_sync.listdir(path):
                            photo_count += 1
                        act.photo_counter = photo_count
                        act.save()
                        break
            self.message_user(request, "Запущен импорт фото")
            return HttpResponseRedirect("../")
        except Exception:
            self.message_user(request, "Что-то пошло не так, попробуйте еще раз.", messages.ERROR)
            return HttpResponseRedirect("../")

    def process_metrics(self, request):
        for i in range(1, models.Photo.objects.count() // BATCH_SIZE + 2):
            PeriodicTask.objects.update_or_create(
                name=f'Добавление метрик на странице {i}',
                task='add_photo_metrics',
                interval=IntervalSchedule.objects.get(
                    every=15, period='minutes'),
                one_off=False,
                defaults={
                    'args': json.dumps([i]),
                    'start_time': datetime.datetime.now() - datetime.timedelta(hours=3),
                }
            )
        self.message_user(request, "Запущен расчет метрик")
        return HttpResponseRedirect("../")

    @admin.action(description='Перенести в корзину')
    def delete_selected(self, request, queryset):
        try:
            date = request.POST.get('date_remove')
            date = datetime.datetime.strptime(date, '%d.%m.%Y')
            for obj in queryset:
                obj.in_trash = True
                obj.save()
                date = date.replace(tzinfo=pytz.timezone('Europe/Moscow'))
                PeriodicTask.objects.update_or_create(
                    name=f'Удаление мероприятия {obj.id}',
                    task='delete_event',
                    interval=IntervalSchedule.objects.get(
                        every=1, period='minutes'),
                    one_off=True,
                    defaults={
                        'args': json.dumps([obj.id]),
                        'start_time': date,
                    }
                )
                email_users.delay(date, obj.id, 'мероприятие')
                try:
                    for event in obj.event.all():
                        models.BasketEvents.objects.create(group_event=obj,
                                                           event=event,
                                                           expired=date)
                        event.in_trash = True
                        event.save()
                        try:
                            for act in event.acts.all():
                                models.BasketEvents.objects.create(group_event=obj,
                                                                   event=event,
                                                                   act=act,
                                                                   expired=date)
                                act.in_trash = True
                                act.save()
                        except:
                            ...
                except:
                    ...

            self.message_user(request,
                              f"{len(queryset)} мероприятие(й) перенесено в корзину. Удаление всех фото произойдет {date}",
                              messages.SUCCESS)
        except Exception:
            self.message_user(request, "Что-то пошло не так, попробуйте снова.", messages.ERROR)

    @admin.action(description='Сделать видимым для пользователей')
    def visible_selected(self, request, queryset):
        try:
            for obj in queryset:
                for event in obj.event.all():
                    for act in event.acts.all():
                        act.visible = True
                        act.save()
                    event.visible = True
                    event.save()
                obj.visible = True
                obj.save()
            self.message_user(request,
                              f"{len(queryset)} мероприятие(й) открылось для просмотра пользователей.",
                              messages.SUCCESS)
        except Exception:
            self.message_user(request, "Что-то пошло не так, попробуйте снова.", messages.ERROR)

    @admin.action(description='Сделать НЕвидимым для пользователей')
    def unvisible_selected(self, request, queryset):
        try:
            for obj in queryset:
                for event in obj.event.all():
                    for act in event.acts.all():
                        act.visible = False
                        act.save()
                    event.visible = False
                    event.save()
                obj.visible = False
                obj.save()
            self.message_user(request,
                              f"{len(queryset)} мероприятие(й) скрыто для просмотра пользователей.",
                              messages.SUCCESS)
        except Exception:
            self.message_user(request, "Что-то пошло не так, попробуйте снова.", messages.ERROR)

    action_form = XForm
    actions = [delete_selected, visible_selected, unvisible_selected]

    def has_add_permission(self, request, obj=None):
        return False


class Event(admin.ModelAdmin):
    fields = [
        ('date', 'get_image_url'),
        'get_metrics_info',
        ('visible', 'in_trash', 'deleted_at')
    ]
    list_display = (
        'get_date',
        'visible',
        'in_trash',
        'get_metrics_info',
        'get_image_url',
        'deleted_at'
    )
    search_fields = [
        'get_date',
        'visible'
    ]
    ordering = ('date', )
    readonly_fields = (
        'date',
        'get_image_url',
        'in_trash',
        'get_metrics_info',
        'deleted_at'
    )
    exclude = ('image_url',)
    list_filter = (GroupEventFilter, )
    inlines = [ActsInline]
    change_list_template = "admin/model_change_list.html"

    def get_date(self, obj):
        return obj.date.astimezone(pytz.timezone('Europe/Moscow')).date()
    get_date.short_description = "Дата проведения"
    get_date.admin_order_field = 'date'

    def deleted_at(self, obj):
        pt = PeriodicTask.objects.filter(name=f'Удаление дня мероприятия {obj.id}')
        if pt.exists():
            return pt.first().start_time
        return '-'
    deleted_at.short_description = 'Дата и время удаления'

    def get_image_url(self, obj):
        return format_html('<img src="/{}" style="max-width: 300px; max-height: 300px;"/>'.format(obj.image_url))
    get_image_url.allow_tags = True
    get_image_url.short_description = "Превью"

    def get_metrics_info(self, obj):
        count = 0
        metrics = 0
        empty = 0
        for act in obj.acts.all():
            count += act.photos.count()
            metrics += act.photos.count() - act.photos.filter(metrics=[]).count()
            empty += act.photos.filter(metrics=[[]]).count()
        return f"{count}/{metrics}/{empty}"
    get_metrics_info.short_description = "Всего фото/обработано/пустые"

    @admin.action(description='Перенести в корзину')
    def delete_selected(self, request, queryset):
        try:
            date = request.POST.get('date_remove')
            date = datetime.datetime.strptime(date, '%d.%m.%Y')
            for obj in queryset:
                for act in obj.acts.all():
                    models.BasketEvents.objects.create(event=obj,
                                                       act=act,
                                                       expired=date)
                    act.in_trash = True
                    act.save()
                obj.in_trash = True
                obj.save()
                date = date.replace(tzinfo=pytz.timezone('Europe/Moscow'))
                PeriodicTask.objects.update_or_create(
                    name=f'Удаление дня мероприятия {obj.id}',
                    task='delete_day_event',
                    interval=IntervalSchedule.objects.get(
                        every=1, period='minutes'),
                    one_off=True,
                    defaults={
                        'args': json.dumps([obj.id]),
                        'start_time': date,
                    }
                )
                email_users.delay(date, obj.id, 'день мероприятия')

            self.message_user(request,
                              f"{len(queryset)} мероприятие(й) перенесено в корзину. Удаление всех фото произойдет {date}",
                              messages.SUCCESS)
        except Exception:
            self.message_user(request, "Что-то пошло не так, попробуйте снова.", messages.ERROR)

    @admin.action(description='Сделать видимым для пользователей')
    def visible_selected(self, request, queryset):
        try:
            for obj in queryset:
                for act in obj.acts.all():
                    act.visible = True
                    act.save()
                obj.visible = True
                obj.save()
            self.message_user(request,
                              f"{len(queryset)} день(дней) открылось для просмотра пользователей.",
                              messages.SUCCESS)
        except Exception:
            self.message_user(request, "Что-то пошло не так, попробуйте снова.", messages.ERROR)

    @admin.action(description='Сделать НЕвидимым для пользователей')
    def unvisible_selected(self, request, queryset):
        try:
            for obj in queryset:
                for act in obj.acts.all():
                    act.visible = False
                    act.save()
                obj.visible = False
                obj.save()
            self.message_user(request,
                              f"{len(queryset)} день(дней) скрыто для просмотра пользователей.",
                              messages.SUCCESS)
        except Exception:
            self.message_user(request, "Что-то пошло не так, попробуйте снова.", messages.ERROR)

    action_form = XForm
    actions = [delete_selected, visible_selected, unvisible_selected]

    def has_add_permission(self, request, obj=None):
        return False


class Act(admin.ModelAdmin):
    fields = [
        'get_event',
        'time',
        'display_groups',
        ('get_photo_counter', 'get_metrics_info'),
        'in_trash',
        'deleted_at'
    ]
    list_display = (
        'display_groups',
        'time',
        'visible',
        'get_photo_counter',
        'get_metrics_info',
        'in_trash',
        'deleted_at'
    )
    list_filter = (GroupEventFilter, EventFilter)
    search_fields = ['display_groups', 'time']
    ordering = ('time', )
    readonly_fields = (
        'get_event',
        'time',
        'display_groups',
        'get_photo_counter',
        'get_metrics_info',
        'in_trash',
        'deleted_at'
    )

    def get_event(self, obj):
        event = obj.event
        event_url = reverse('admin:Catalog_groupevent_change', args=[event.group_id])
        return format_html('<a href="{}">{}</a>', event_url, f"{event.group.title} {event.group.sub_title}")
    get_event.short_description = "Мероприятие"

    def deleted_at(self, obj):
        pt = PeriodicTask.objects.filter(name=f'Удаление концерта {obj.id}')
        if pt.exists():
            return pt.first().start_time
        return '-'
    deleted_at.short_description = 'Дата и время удаления'

    def get_photo_counter(self, obj):
        return f"{models.Photo.objects.filter(act=obj).count()}/{obj.photo_counter}"
    get_photo_counter.short_description = "Импортировано/Всего фото"

    def display_groups(self, obj):
        groups = eval(obj.groups)
        groups_str = ', '.join(groups)
        return mark_safe(groups_str)
    display_groups.short_description = "Студии-школы"

    def get_metrics_info(self, obj):
        count = obj.photos.count()
        metrics = obj.photos.count() - obj.photos.filter(metrics=[]).count()
        empty = obj.photos.filter(metrics=[[]]).count()
        return f"{count}/{metrics}/{empty}"
    get_metrics_info.short_description = "Всего фото/обработано/пустые"

    @admin.action(description='Перенести в корзину')
    def delete_selected(self, request, queryset):
        try:
            date = request.POST.get('date_remove')
            date = datetime.datetime.strptime(date, '%d.%m.%Y')
            for obj in queryset:
                models.BasketEvents.objects.create(event=obj.event,
                                                   act=obj,
                                                   expired=date)
                obj.in_trash = True
                obj.save()
                date = date.replace(tzinfo=pytz.timezone('Europe/Moscow'))
                PeriodicTask.objects.update_or_create(
                    name=f'Удаление концерта {obj.id}',
                    task='delete_consert',
                    interval=IntervalSchedule.objects.get(
                        every=1, period='minutes'),
                    one_off=True,
                    defaults={
                        'args': json.dumps([obj.id]),
                        'start_time': date,
                    }
                )
                email_users.delay(date, obj.id, 'концерт')

            self.message_user(request,
                              f"{len(queryset)} концерт(ов) перенесено в корзину. Удаление всех фото произойдет {date}",
                              messages.SUCCESS)
        except Exception:
            self.message_user(request, "Что-то пошло не так, попробуйте снова.", messages.ERROR)

    @admin.action(description='Сделать видимым для пользователей')
    def visible_selected(self, request, queryset):
        try:
            for obj in queryset:
                obj.visible = True
                obj.save()
            self.message_user(request,
                              f"{len(queryset)} концерт(ов) открылось для просмотра пользователей.",
                              messages.SUCCESS)
        except Exception:
            self.message_user(request, "Что-то пошло не так, попробуйте снова.", messages.ERROR)

    @admin.action(description='Сделать НЕвидимым для пользователей')
    def unvisible_selected(self, request, queryset):
        try:
            for obj in queryset:
                obj.visible = False
                obj.save()
            self.message_user(request,
                              f"{len(queryset)} концерт(ов) скрыто для просмотра пользователей.",
                              messages.SUCCESS)
        except Exception:
            self.message_user(request, "Что-то пошло не так, попробуйте снова.", messages.ERROR)

    action_form = XForm
    actions = [delete_selected, visible_selected, unvisible_selected]

    def has_add_permission(self, request, obj=None):
        return False


class Photo(admin.ModelAdmin):
    fields = [
        ('name', 'act'),
        ('get_preview_url', 'get_preview_watermark_url'),
        ('get_photo_orient', 'get_metrics_info'),
        ('in_trash', 'deleted_at')
    ]
    list_display = (
        'name',
        'get_photo_orient',
        'get_metrics_info',
        'get_preview_url',
        'get_preview_watermark_url',
        'in_trash',
        'deleted_at'
    )
    search_fields = ['name']
    list_filter = (GroupEventFilter, EventFilter, ActFilter)
    ordering = ('name', )
    readonly_fields = (
        'name',
        'act',
        'get_photo_orient',
        'get_preview_url',
        'get_preview_watermark_url',
        'get_metrics_info',
        'in_trash',
        'deleted_at'
    )
    max_num = 100

    def get_photo_orient(self, obj):
        return "Вертикальная" if obj.photo_orient else "Горизонтальная"
    get_photo_orient.short_description = "Ориентация"

    def get_preview_url(self, obj):
        return format_html('<img src="/{}" style="max-width: 300px; max-height: 300px;"/>'.format(obj.preview_url_host))
    get_preview_url.allow_tags = True
    get_preview_url.short_description = "Превью"

    def get_preview_watermark_url(self, obj):
        return format_html('<img src="/{}" style="max-width: 300px; max-height: 300px;"/>'.format(obj.preview_watermark_url_host))
    get_preview_watermark_url.allow_tags = True
    get_preview_watermark_url.short_description = "Превью с водным знаком"

    def get_metrics_info(self, obj):
        return True if obj.metrics != [] and obj.metrics != [[]] else False
    get_metrics_info.short_description = "Метрики сняты"
    get_metrics_info.boolean = True

    @admin.action(description='Перенести в корзину')
    def delete_selected(self, request, queryset):
        try:
            date = request.POST.get('date_remove')
            date = datetime.datetime.strptime(date, '%d.%m.%Y')
            for obj in queryset:
                models.BasketEvents.objects.create(event=obj.act.event,
                                                   act=obj.act,
                                                   photo=obj,
                                                   expired=date)
                obj.in_trash = True
                obj.save()
                date = date.replace(tzinfo=pytz.timezone('Europe/Moscow'))
                PeriodicTask.objects.update_or_create(
                    name=f'Удаление фото {obj.id}',
                    task='delete_photo',
                    interval=IntervalSchedule.objects.get(
                        every=1, period='minutes'),
                    one_off=True,
                    defaults={
                        'args': json.dumps([obj.id]),
                        'start_time': date,
                    }
                )
                email_users.delay(date, obj.id, 'фото')

            self.message_user(request,
                              f"{len(queryset)} фото перенесено в корзину. Удаление всех фото произойдет {date}",
                              messages.SUCCESS)
        except Exception:
            self.message_user(request, "Что-то пошло не так, попробуйте снова.", messages.ERROR)

    action_form = XForm
    actions = [delete_selected]

    def has_add_permission(self, request, obj=None):
        return False


admin.site.register(models.GroupEvent, GroupEvent)
admin.site.register(models.Event, Event)
admin.site.register(models.Act, Act)
admin.site.register(models.Photo, Photo)
