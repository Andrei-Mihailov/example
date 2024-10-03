import datetime
import pytz
import locale

from django.db import models
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

locale.setlocale(locale.LC_ALL, 'ru_RU.utf-8')


class GroupEvent(models.Model):
    title = models.CharField(verbose_name='Заголовок',
                             max_length=255)
    sub_title = models.CharField(verbose_name='Подзаголовок',
                                 max_length=255)
    image_url = models.URLField(verbose_name='Превью',
                                max_length=500)
    price = models.PositiveIntegerField(verbose_name='Стоимость фото',
                                        null=True,
                                        blank=True)
    base_sale = models.PositiveIntegerField(verbose_name='Цена со скидкой на фото',
                                            null=True,
                                            blank=True)
    sale_price_1_limit = models.PositiveIntegerField(verbose_name='Количество фото для скидки 1',
                                                     default=10)
    sale_price_1 = models.PositiveIntegerField(verbose_name='Cкидка 1, %',
                                               default=5)
    sale_price_2_limit = models.PositiveIntegerField(verbose_name='Количество фото для скидки 2',
                                                     default=15)
    sale_price_2 = models.PositiveIntegerField(verbose_name='Cкидка 2, %',
                                               default=10)
    visible = models.BooleanField(verbose_name='Видимость для пользователей',
                                  default=False)
    in_trash = models.BooleanField(verbose_name='В корзине',
                                   default=False)

    def __str__(self):
        return f"{self.title} {self.sub_title}"

    class Meta:
        verbose_name = 'Мероприятие'
        verbose_name_plural = 'Мероприятия'


class Event(models.Model):
    date = models.DateTimeField(verbose_name='Дата проведения')

    image_url = models.URLField(verbose_name='Превью',
                                max_length=500)
    group = models.ForeignKey(GroupEvent,
                              default=1,
                              verbose_name="Группа",
                              related_name='event',
                              on_delete=models.CASCADE)
    visible = models.BooleanField(verbose_name='Видимость для пользователей',
                                  default=False)
    in_trash = models.BooleanField(verbose_name='В корзине',
                                   default=False)

    def __str__(self):
        return self.date.astimezone(pytz.timezone('Europe/Moscow')).strftime('%d %B %Y')

    class Meta:
        verbose_name = 'День мероприятия'
        verbose_name_plural = 'Дни мероприятия'


class Act(models.Model):
    event = models.ForeignKey(Event,
                              verbose_name="Мероприятие",
                              related_name='acts',
                              on_delete=models.CASCADE)
    time = models.DateTimeField(verbose_name='Дата и время')
    groups = models.JSONField(verbose_name='Локации',)
    photo_counter = models.PositiveIntegerField(verbose_name='Количество фото',
                                                null=True)
    visible = models.BooleanField(verbose_name='Видимость для пользователей',
                                  default=False)
    in_trash = models.BooleanField(verbose_name='В корзине',
                                   default=False)

    def __str__(self):
        return f"Концерт {self.event.group.title} {self.event.group.sub_title} {self.time.astimezone(pytz.timezone('Europe/Moscow')).strftime('%d %B %Y')}"

    class Meta:
        verbose_name = 'Концерт'
        verbose_name_plural = 'Концерты'


class Photo(models.Model):
    preview_url = models.URLField(max_length=500)
    preview_watermark_url = models.URLField(max_length=500)
    preview_url_host = models.URLField(max_length=500,
                                       default=None,
                                       null=True)
    preview_watermark_url_host = models.URLField(max_length=500,
                                                 default=None,
                                                 null=True)
    original_url = models.URLField(max_length=500)
    # вертикальная ориентация = 1, горизонтальная = 0
    photo_orient = models.PositiveSmallIntegerField()
    name = models.CharField(verbose_name='Название файла',
                            max_length=100)
    metrics = models.JSONField(null=True,
                               default=None)
    act = models.ForeignKey(Act,
                            verbose_name='Концерт',
                            related_name='photos',
                            on_delete=models.CASCADE)
    in_trash = models.BooleanField(verbose_name='В корзине',
                                   default=False)
    deleted_at = models.DateTimeField(null=True,
                                      verbose_name='Дата и время удаления')

    def __str__(self):
        return f"Фото мероприятия {self.act.event.group.title}"

    class Meta:
        verbose_name = 'Фото'
        verbose_name_plural = 'Фото'
        unique_together = ('name', 'act')


class PhotoSearchResult(models.Model):
    sample_photo_url = models.URLField(max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Результаты поиска {self.uploaded_at}"


class PhotoMatch(models.Model):
    photo = models.ManyToManyField(Photo)
    search_photo = models.ForeignKey(PhotoSearchResult,
                                     related_name='matches',
                                     on_delete=models.CASCADE)
    confidence_score = models.FloatField()

    def __str__(self):
        return f"Совпадения для {self.photo.preview_url}"


class BasketEvents(models.Model):
    group_event = models.ForeignKey(GroupEvent,
                                    on_delete=models.CASCADE,
                                    default=None,
                                    null=True)
    event = models.ForeignKey(Event,
                              on_delete=models.CASCADE,
                              default=None,
                              null=True)
    act = models.ForeignKey(Act,
                            on_delete=models.CASCADE,
                            default=None,
                            null=True)
    photo = models.ForeignKey(Photo,
                              on_delete=models.CASCADE,
                              default=None,
                              null=True)
    expired = models.DateTimeField(verbose_name='Дата удаления из корзины',
                                   default=None,
                                   blank=False,
                                   null=False)

    def save(self, *args, **kwargs):
        if not self.expired:
            self.expired = datetime.datetime.now() + datetime.timedelta(days=365)

        return super(BasketEvents, self).save()


class ColorsEvent(models.Model):
    group_event = models.ForeignKey(GroupEvent,
                                    related_name='ColorEvent',
                                    on_delete=models.CASCADE,
                                    default=None,
                                    null=True)
    theme_name = models.CharField(max_length=20, default="White")
    color_main = models.CharField(max_length=20, default="255,255,255")
    color_start = models.CharField(max_length=20, default="255,255,255")
    color_end = models.CharField(max_length=20, default="255,255,255")

    def __str__(self):
        return self.theme_name

    def save(self, *args, **kwargs):
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')

            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)

            return f"{r},{g},{b}"

        self.color_main = hex_to_rgb(self.color_main) if '#' in self.color_main else self.color_main
        self.color_start = hex_to_rgb(self.color_start) if '#' in self.color_start else self.color_start
        self.color_end = hex_to_rgb(self.color_end) if '#' in self.color_end else self.color_end
        return super(ColorsEvent, self).save()


@receiver(post_save, sender=BasketEvents)
def update_photos_deleted_at(sender, instance, created, **kwargs):
    if created:
        # Если указано отдельное фото
        if instance.photo:
            instance.photo.deleted_at = timezone.now()
            instance.photo.save()

        # Обновляем дату удаления для фотографий, связанных с конкретным событием
        if instance.act:
            for photo in instance.act.photos.all():
                photo.deleted_at = timezone.now()
                photo.save()

        # Если есть события, то обновляем также для мероприятий
        if instance.event:
            for act in instance.event.acts.all():
                for photo in act.photos.all():
                    photo.deleted_at = timezone.now()
                    photo.save()

        # Если есть группа мероприятий, обновляем для всех событий в группе
        if instance.group_event:
            for event in instance.group_event.event.all():
                for act in event.acts.all():
                    for photo in act.photos.all():
                        photo.deleted_at = timezone.now()
                        photo.save()
