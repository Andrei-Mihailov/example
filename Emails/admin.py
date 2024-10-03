import datetime
import imaplib
import json

from django.contrib import admin
from django.utils.html import format_html
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from django.contrib import messages
from django import forms

from . import models
from .forms import ReplyEmailForm
from .custom_filters import Sender
from Mydance.settings import EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD


try:
    PeriodicTask.objects.update_or_create(
        name='Сборщик писем',
        task='check_emails',
        interval=IntervalSchedule.objects.get(
            every=15, period='minutes'),
        one_off=False,
        defaults={
            'start_time': datetime.datetime.now(),
        }
    )
except:
    ...
admin.site.disable_action('delete_selected')


def is_html(text):
    if any(tag in text for tag in ['<html>', '<head>', '<body>', '<div>', '<p>']):
        return True
    return False


class EmailsInline(admin.TabularInline):
    model = models.Emails

    fields = [
        'sender',
        'receiver',
        'subject',
        'get_message',
        'time',
    ]
    readonly_fields = (
        'sender',
        'receiver',
        'subject',
        'get_message',
        'time',
    )

    extra = 0
    show_change_link = True
    verbose_name = "Ответ на сообщение"
    verbose_name_plural = "Ответ на сообщение"

    def get_message(self, request):
        if is_html(request.message):
            return format_html(request.message)
        else:
            return request.message
    get_message.allow_tags = True
    get_message.short_description = "Сообщение"

    def has_add_permission(self, request, obj=None):
        return False


class CustomEmailsForm(forms.ModelForm):
    class Meta:
        model = models.Emails
        fields = '__all__'


class Emails(admin.ModelAdmin):
    form = CustomEmailsForm
    fields = [
        'time',
        'subject',
        'get_message',
    ]
    list_display = (
        'sender',
        'replyed',
        'subject',
        'get_message',
        'time',
    )
    search_fields = [
        'sender',
        'subject',
        'get_message'
    ]
    ordering = ('sender', 'time')
    readonly_fields = (
        'sender',
        'receiver',
        'subject',
        'get_message',
        'time',
    )
    inlines = [EmailsInline]
    list_filter = (Sender, )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.order_by("-time")
        return qs

    def get_message(self, request):
        if is_html(request.message):
            return format_html(request.message)
        else:
            return request.message
    get_message.allow_tags = True
    get_message.short_description = "Сообщение"

    @admin.action(description='Удалить выбранные')
    def delete_action(self, request, queryset):
        if request.POST.get('action') == 'delete_action':
            imap = imaplib.IMAP4_SSL(EMAIL_HOST)
            imap.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
            imap.select('INBOX')
            selected_ids = request.POST.getlist('_selected_action')
            selected_emails = queryset.filter(pk__in=selected_ids)
            for email in selected_emails:
                if email.in_box_id:
                    try:
                        imap.store(str(email.in_box_id).encode(), '+FLAGS', '\\Deleted')
                    except Exception:
                        ...
                email.delete()
            imap.expunge()
        else:
            return self.send_ads_action(request, queryset)

    @admin.action(description='Ответить на Письмо')
    def response_action(self, request, queryset):
        if request.POST.get('action') == 'response_action':
            message = request.POST.get('message')
            subject = request.POST.get('subject')

            selected_ids = request.POST.getlist('_selected_action')
            selected_emails = queryset.filter(pk__in=selected_ids)
            try:
                for email in selected_emails:
                    if not subject:
                        subject = 'Re: ' + email.subject.replace("Re: ", "")
                    models.Emails.objects.create(sender=email.receiver,
                                                 receiver=email.sender,
                                                 reply_to=email,
                                                 subject=subject,
                                                 message=message)
                    email.replyed = True
                    email.save()
                self.message_user(request,
                                  "Сообщение успешно отправлено",
                                  messages.SUCCESS)
            except Exception:
                self.message_user(request,
                                  "Возникла ошибка при отправке сообщения",
                                  messages.ERROR)
        else:
            return self.delete_action(request, queryset)

    @admin.action(description='Сделать рассылку всем')
    def send_ads_action(self, request, queryset):
        message = request.POST.get('message')
        subject = request.POST.get('subject')
        try:
            PeriodicTask.objects.update_or_create(
                name='Рассылка email',
                task='sender_emails',
                interval=IntervalSchedule.objects.get(
                    every=1, period='hours'),
                one_off=True,
                defaults={
                    'kwargs': json.dumps({'subject': subject, 'message': message}),
                    'start_time': datetime.datetime.now(),
                }
            )
            self.message_user(request,
                              "Задание рассылки успешно создано",
                              messages.SUCCESS)
        except Exception:
            self.message_user(request,
                              "Возникла ошибка при создании задания рассылки",
                              messages.ERROR)

    action_form = ReplyEmailForm
    actions = [delete_action, response_action, send_ads_action]

    def has_add_permission(self, request, obj=None):
        return False


admin.site.register(models.Emails, Emails)
