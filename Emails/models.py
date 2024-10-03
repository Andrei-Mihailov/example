import datetime

from django.db import models
from django.core.mail import send_mail, EmailMessage


class Contact(models.Model):
    first_name = models.CharField(verbose_name='Имя',
                                  max_length=200)
    phone = models.CharField(verbose_name='Телефон',
                             max_length=200)
    email = models.EmailField(max_length=200)

    def __str__(self):
        return self.email

    def email_user(self, subject, message, from_email=None, **kwargs):
        send_mail(subject, message, from_email, [self.email], **kwargs)


class Emails(models.Model):
    message_id = models.CharField(primary_key=True,
                                  max_length=255,
                                  default='1',
                                  unique=True)
    in_box_id = models.IntegerField(verbose_name='Айди в почтовом ящике',
                                    default=0)
    sender = models.ForeignKey(Contact,
                               verbose_name='Отправитель',
                               related_name='sent_emails',
                               on_delete=models.CASCADE)
    receiver = models.ForeignKey(Contact,
                                 verbose_name='Получатель',
                                 related_name='received_emails',
                                 on_delete=models.CASCADE)
    subject = models.CharField(verbose_name='Тема',
                               default=None,
                               null=True,
                               max_length=500)
    message = models.TextField(verbose_name="Сообщение",
                               max_length=2000)
    from_box = models.BooleanField(default=False)
    time = models.DateTimeField(verbose_name="Дата и время получения")
    reply_to = models.ForeignKey('self',
                                 verbose_name='Ответ на',
                                 null=True,
                                 blank=True,
                                 on_delete=models.SET_NULL)
    replyed = models.BooleanField(verbose_name='Отвечено',
                                  default=False)

    def __str__(self):
        return f'From: {self.sender.email} | To: {self.receiver.email}'

    def save(self, *args, **kwargs):
        if not self.time:
            self.time = datetime.datetime.now()
        if not self.from_box:
            if not self.subject:
                self.subject = 'Support'
            if self.sender.email.endswith('@mydance.photo'):
                from_email = f"Техподдержка сайта mydance.photo <{self.sender.email}>"
            else:
                from_email = f"{self.sender.first_name} <{self.sender.email}>"
            email = EmailMessage(
                subject=self.subject,
                body=self.message,
                from_email=from_email,
                to=[self.receiver],
                headers={
                    "In-Reply-To": self.reply_to_id,
                    "References": self.reply_to_id
                }
            )
            email.send()
            self.message_id = email.message().get('Message-ID')
        return super(Emails, self).save()

    class Meta:
        verbose_name = 'Письмо'
        verbose_name_plural = 'Письма'
