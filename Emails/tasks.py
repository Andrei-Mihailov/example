
import imaplib
import email
import email.message
import time
import quopri
import datetime
import base64

from django_celery_beat.models import PeriodicTask
from django.core.mail import send_mail
from email.header import decode_header
from celery import shared_task
from imbox import Imbox

from Mydance.settings import EMAIL_HOST, EMAIL_HOST_POP3, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD
from Emails.models import Contact, Emails
from Users.models import Users
from api.emails import email_sender


@shared_task(name="check_emails")
def check_emails():
    with Imbox(EMAIL_HOST_POP3,
               username=EMAIL_HOST_USER,
               password=EMAIL_HOST_PASSWORD,
               ssl=True,
               ssl_context=None,
               starttls=False) as imbox:
        all_inbox_messages = imbox.messages()
        imap = imaplib.IMAP4_SSL(EMAIL_HOST)
        imap.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
        imap.select('INBOX')
        _, search_data = imap.search(None, 'ALL')
        for (_, message), msg_id in zip(all_inbox_messages, search_data[0].split()):
            name = message.sent_from[0]['name']
            msg_id_str = msg_id.decode('utf-8')
            _, msg_data = imap.fetch(msg_id_str, '(RFC822)')
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            message_id = msg['Message-ID']
            if not Emails.objects.filter(message_id=message_id).exists():
                # Извлечение информации из письма
                sender = msg['Return-Path']
                subject = decode_header(msg['Subject'])[0][0]
                try:
                    subject = subject.decode('utf-8')
                except Exception:
                    ...
                timestamp = email.utils.parsedate_tz(msg['Date'])
                dt_message = datetime.datetime.fromtimestamp(time.mktime(timestamp[:-1]))
                in_reply_to = msg['In-Reply-To']

                # Извлечение текста письма
                email_body = ''
                if msg.is_multipart():
                    for part in msg.get_payload():
                        if part.get_content_type() == 'text/plain':
                            try:
                                email_body += base64.b64decode(part.get_payload()).decode('utf-8')
                            except Exception:
                                email_body += quopri.decodestring(part.get_payload()).decode()
                else:

                    try:
                        email_body = quopri.decodestring(msg.get_payload()).decode()
                    except Exception:
                        email_body = msg.get_payload()

                support = Contact.objects.first()
                user, _ = Contact.objects.get_or_create(email=sender,
                                                        defaults={
                                                            'first_name': name
                                                        })
                try:
                    reply_to = Emails.objects.get(message_id__contains=in_reply_to.split('.')[1]).message_id
                except Exception:
                    reply_to = None
                Emails.objects.create(
                    message_id=message_id,
                    in_box_id=msg_id_str,
                    sender=user,
                    reply_to_id=reply_to,
                    subject=subject,
                    time=dt_message,
                    receiver=support,
                    message=email_body,
                    from_box=True,
                    replyed=True if b'\\Answered' in message.flags else False
                )


@shared_task(name="sender_emails")
def sender_emails(**kwargs):
    subject = kwargs.get('subject')
    message = kwargs.get('message')
    users = Users.objects.filter(email_notifications=True)
    for user in users:
        try:
            send_mail(subject=subject,
                      message=None,
                      html_message=email_sender(user, message),
                      from_email="Новости от mydance.photo <info@mydance.photo>",
                      recipient_list=[user.email])
        except Exception:
            ...
    PeriodicTask.objects.get(name='Рассылка email').delete()
