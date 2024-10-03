import os
import time
import pytz
import asyncio
import json
import datetime
import aiohttp
import requests
import face_recognition
import zipfile

from celery import shared_task
from yadisk.exceptions import PathNotFoundError
from django.core.paginator import Paginator
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from channels.db import database_sync_to_async
from PIL import Image
from io import BytesIO


from Catalog.models import GroupEvent, Photo, Event, Act, BasketEvents
from Basket.models import Order
from api.utils import PrintException
from api.emails import email_photos_remove
from Mydance.config import headers, rus_months, prefix_concerts, client_sync, client
from Mydance.settings import PREPEND_PATH
from .utils import (format_path, get_or_create_group_event, get_or_create_event,
                    get_or_create_act, get_or_create_photo, save_previews_to_disk,
                    watermark_photo, remove_dir, DataMigrator)


base_dir = 'disk:/watermark/'
BATCH_SIZE = 1000


async def face_rec_async(image_url):
    try:
        start_time = time.time()
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url, headers=headers) as response:
                image = BytesIO(await response.content.read())
                end_time = time.time()
                print(f"Время загрузки фото: {end_time - start_time} секунд")
                start_time = time.time()
                faces_numpy = face_recognition.load_image_file(image)
                face_numpy_encodings = face_recognition.face_encodings(
                    faces_numpy)
                end_time = time.time()
                print(f"Время обработки фото: {end_time - start_time} секунд")
                return face_numpy_encodings
    except Exception:
        print("Не может распознать лица")


def face_rec(image_url):
    try:
        start_time = time.time()
        with requests.Session() as session:
            response = session.get(image_url, headers=headers)
            image = BytesIO(response.content)
            end_time = time.time()
            print(f"Время загрузки фото: {end_time - start_time} секунд")
            start_time = time.time()
            faces_numpy = face_recognition.load_image_file(image)
            face_numpy_encodings = face_recognition.face_encodings(
                faces_numpy)
            end_time = time.time()
            print(f"Время обработки фото: {end_time - start_time} секунд")
            return face_numpy_encodings
    except Exception:
        print("Не может распознать лица")


def save_models(path, file, preview_url, preview_watermark_url, photo_orient, metrics_):
    event_title, event_sub_title, event_date, act_groups, act_time = format_path(
        path)
    try:

        group, _ = get_or_create_group_event(event_title, event_sub_title)
        event, _ = get_or_create_event(event_date, group)
        act, _ = get_or_create_act(event, act_time, act_groups)
        photo, _ = get_or_create_photo(act, preview_url, preview_watermark_url, file, photo_orient, metrics_)
        photo = save_previews_to_disk(photo)
        if not event.image_url:
            event.image_url = photo.preview_url_host
            event.save()
        if not group.image_url:
            event.image_url = photo.preview_url_host
            event.save()
        return photo
    except Exception as e:
        print(e)


def file_exist(file, path):
    _, _, _, act_groups, act_time = format_path(path)
    act = Act.objects.filter(time=act_time,
                             groups=act_groups)
    if act.exists():
        return Photo.objects.filter(act=act.first(), name=file['name']).exists()
    else:
        return False


@shared_task(name="import_files")
def import_files(main_path):
    folder = main_path.split('/')[-1]
    migrator = DataMigrator(state_file=f"logs/{folder}.json")
    state = migrator.load_state()
    counter = state["offset"]
    print(f"Началась обработка папки {folder}")
    for file in client_sync.listdir(main_path):
        if 'watermark' in main_path:
            counter += 1
            state["offset"] = counter
            migrator.save_state(state)
            continue
        if file_exist(file, main_path):
            counter += 1
            state["offset"] = counter
            migrator.save_state(state)
            print(f"Пропуск уже существующих фото {counter}")
            continue

        output_image_path = base_dir + main_path

        # создание директории если нет
        if not client_sync.exists(output_image_path, timeout=5):
            new_dir = base_dir
            for part_path in output_image_path.replace(base_dir, '').split('/'):
                new_dir += part_path
                if not client_sync.exists(new_dir, timeout=5):
                    client_sync.mkdir(new_dir, timeout=5)
                new_dir += '/'

        photo_orient, preview_url = watermark_photo(
            file['preview'], output_image_path + '/' + file['name'])

        metrics = []
        metrics_ = []
        for metric in metrics:
            metrics_.append(metric.tolist())
        while True:
            try:
                preview_watermark = client_sync.get_meta(output_image_path + '/' + file['name'])
                if photo_orient:
                    preview_watermark_url = preview_watermark['preview'].replace('size=S', 'size=467x700')
                else:
                    preview_watermark_url = preview_watermark['preview'].replace('size=S', 'size=700x467')
                break
            except Exception:
                ...
        save_models(main_path, file, preview_url,
                    preview_watermark_url, photo_orient, metrics_)
        counter += 1
        state["offset"] = counter
        migrator.save_state(state)
        print(f"save {counter} - {folder} - {file['name']}")
    event_title, event_sub_title, event_date, act_groups, act_time = format_path(main_path)
    group, _ = get_or_create_group_event(event_title, event_sub_title)
    event, _ = get_or_create_event(event_date, group)
    act, _ = get_or_create_act(event, act_time, act_groups)
    set_photo_count(act)


def set_photo_count(act):
    photo_count = Photo.objects.filter(act=act).count()
    act.photo_counter = photo_count
    act.save()


async def change_photo_link(count_in):
    migrator = DataMigrator(state_file=f"logs/links_{count_in}.json")
    state = migrator.load_state()
    counter = state["offset"]
    if count_in > counter:
        counter = count_in
    print("получаем все фото на странице")
    photos = await get_paginated_photos(count_in)
    for photo in photos:
        act: Act = await get_act(photo.act_id)
        time = act.time
        month = time.month
        month_str = list(rus_months.keys())[month - 1]
        date_str = datetime.datetime.strftime(time.astimezone(pytz.timezone('Europe/Moscow')), "%d") + ' ' + month_str
        time_str = datetime.datetime.strftime(time.astimezone(pytz.timezone('Europe/Moscow')), "%H%M")
        for num in prefix_concerts:
            path = f"disk:/watermark/{act.event.group.title}_{act.event.group.sub_title}/{date_str}/{num}_{'_'.join(json.loads(act.groups))}_{time_str}/{photo.name}"
            try:
                res = client_sync.get_meta(path)
                if photo.photo_orient:
                    preview_watermark_url = res['preview'].replace('size=S', 'size=467x700')
                else:
                    preview_watermark_url = res['preview'].replace('size=S', 'size=700x467')
                photo.preview_watermark_url = preview_watermark_url
                await save_photo(photo)
                print(f"save {photo.pk}")
                counter += 1
                state["offset"] = counter
                migrator.save_state(state)
                break
            except Exception:
                ...


def photo_generator(counter):
    photos = Photo.objects.all()
    for photo in photos[counter:]:
        yield photo


@database_sync_to_async
def get_all_photo():
    return list(Photo.objects.all())


async def async_photo_generator(start, end):
    photos = await get_all_photo()
    for photo in photos[start: end]:
        yield photo


@database_sync_to_async
def get_act(act_id):
    return Act.objects.get(id=act_id)


@database_sync_to_async
def save_photo(photo):
    photo.save()


@shared_task(name="add_photo_metrics")
def add_photo_metrics(count_in):
    print(f"process page {count_in}")
    migrator = DataMigrator(state_file=f"logs/metrics_page_{count_in}.json")
    state = migrator.load_state()
    counter = state["offset"]
    photos = get_paginated_photos(count_in)
    try:
        for photo in photos:
            if counter >= photos[-1].pk:
                PeriodicTask.objects.get(name=f'Добавление метрик на странице {count_in}').delete()
                return
            elif counter > photo.pk:
                continue
            if photo.metrics != [] and photo.metrics != [[]]:
                counter = photo.pk
                state["offset"] = counter
                migrator.save_state(state)
                print(f"пропуск {photo.pk} page {count_in}")
                continue
            act = Act.objects.get(id=photo.act_id)
            time = act.time
            month = time.month
            month_str = list(rus_months.keys())[month - 1]
            date_str = datetime.datetime.strftime(time.astimezone(
                pytz.timezone('Europe/Moscow')), "%d") + ' ' + month_str
            time_str = datetime.datetime.strftime(time.astimezone(pytz.timezone('Europe/Moscow')), "%H%M")
            for num in prefix_concerts:
                path = f"disk:/{act.event.group.title}_{act.event.group.sub_title}/{date_str}/{num}_{'_'.join(json.loads(act.groups))}_{time_str}/{photo.name}"
                try:
                    res = client_sync.get_meta(path)
                    metrics = face_rec(res['file'])
                    metrics_ = []
                    if metrics:
                        for metric in metrics:
                            metrics_.append(metric.tolist())
                    photo.metrics = metrics_,
                    photo.save()
                    print(f"save {photo.pk}  page {count_in}")
                    counter = photo.pk
                    state["offset"] = counter
                    migrator.save_state(state)
                    break
                except PathNotFoundError:
                    ...
                except Exception:
                    break
        PeriodicTask.objects.get(name=f'Добавление метрик на странице {count_in}').delete()
    except Exception:
        PrintException()


def get_paginated_photos(page_num):
    paginator = Paginator(Photo.objects.all(), BATCH_SIZE)
    page = paginator.page(page_num)
    return list(page.object_list)


@database_sync_to_async
def async_get_paginated_photos(page_num):
    print(Photo.objects.count())
    paginator = Paginator(Photo.objects.all(), BATCH_SIZE)
    page = paginator.page(page_num)
    return list(page.object_list)


async def async_add_photo_metrics(page):
    try:
        migrator = DataMigrator(state_file=f"logs/metrics_page_{page}.json")
        state = migrator.load_state()
        counter = state["offset"]
        if counter > BATCH_SIZE:
            return
        print(f"получаем все фото на странице {page}")
        photos = await async_get_paginated_photos(page)
        for photo in photos:
            if photo.metrics != [] and photo.metrics != [[]]:
                counter += 1
                state["offset"] = counter
                migrator.save_state(state)
                print(f"пропуск {photo.pk} page {page}")
                continue
            act: Act = await get_act(photo.act_id)
            time = act.time
            month = time.month
            month_str = list(rus_months.keys())[month - 1]
            date_str = datetime.datetime.strftime(time.astimezone(
                pytz.timezone('Europe/Moscow')), "%d") + ' ' + month_str
            time_str = datetime.datetime.strftime(time.astimezone(pytz.timezone('Europe/Moscow')), "%H%M")
            for num in prefix_concerts:
                path = f"disk:/{act.event.group.title}_{act.event.group.sub_title}/{date_str}/{num}_{'_'.join(json.loads(act.groups))}_{time_str}/{photo.name}"
                try:
                    res = await client.get_meta(path)
                    metrics = await face_rec_async(res['file'])
                    metrics_ = []
                    if metrics:
                        for metric in metrics:
                            metrics_.append(metric.tolist())
                    photo.metrics = metrics_,
                    await save_photo(photo)
                    print(f"save {photo.pk}  page {page}")
                    counter += 1
                    state["offset"] = counter
                    migrator.save_state(state)
                    break
                except Exception:
                    counter -= 1
                    state["offset"] = counter
                    migrator.save_state(state)
    except Exception:
        PrintException()


idx = [i * 5650 for i in range(8)]


async def run_photo_metrics():
    print(f"создаем задачи для {[i for i in range(1, 5)]}")
    tasks = [async_add_photo_metrics(i) for i in range(1, 5)]
    await asyncio.gather(*tasks)


@shared_task(name="delete_event")
def delete_event(group_event_id):
    group_event = GroupEvent.objects.get(id=group_event_id)
    BasketEvents.objects.filter(group_event=group_event).delete()
    path = f"{group_event.title}_{group_event.sub_title}"
    if client_sync.is_dir(path):
        client_sync.remove(f'watermark/{path}')
        remove_dir(f"media/original/{path}")
        remove_dir(f"media/watermark/{path}")
    group_event.delete()
    PeriodicTask.objects.get(name=f'Удаление мероприятия {group_event_id}').delete()


@shared_task(name="delete_day_event")
def delete_day_event(event_id):
    event = Event.objects.get(id=event_id)
    BasketEvents.objects.filter(event=event).delete()
    time = event.date
    month = time.month
    month_str = list(rus_months.keys())[month - 1]
    date_str = datetime.datetime.strftime(time.astimezone(pytz.timezone('Europe/Moscow')), "%d") + ' ' + month_str
    if date_str[0] == '0':
        date_str = date_str[1:]
    path = f"{event.group.title}_{event.group.sub_title}/{date_str}"
    if client_sync.is_dir(path):
        client_sync.remove(f'watermark/{path}')
        remove_dir(f"media/original/{path}")
        remove_dir(f"media/watermark/{path}")
    event.delete()
    PeriodicTask.objects.get(name=f'Удаление дня мероприятия {event_id}').delete()


@shared_task(name="delete_consert")
def delete_consert(act_id):
    act = Act.objects.get(id=act_id)
    BasketEvents.objects.filter(act=act).delete()
    time = act.time
    month = time.month
    month_str = list(rus_months.keys())[month - 1]
    date_str = datetime.datetime.strftime(time.astimezone(pytz.timezone('Europe/Moscow')), "%d") + ' ' + month_str
    if date_str[0] == '0':
        date_str = date_str[1:]
    time_str = datetime.datetime.strftime(time.astimezone(pytz.timezone('Europe/Moscow')), "%H%M")
    for num in prefix_concerts:
        path = f"{act.event.group.title}_{act.event.group.sub_title}/{date_str}/{num}_{'_'.join(json.loads(act.groups))}_{time_str}"
        try:
            client_sync.get_meta(path)
            client_sync.remove(f'watermark/{path}')
            remove_dir(f"media/original/{path}")
            remove_dir(f"media/watermark/{path}")
            break
        except Exception:
            ...
    act.delete()
    PeriodicTask.objects.get(name=f'Удаление концерта {act_id}').delete()


@shared_task(name="delete_photo")
def delete_photo(photo_id):
    photo = Photo.objects.get(id=photo_id)
    BasketEvents.objects.filter(photo=photo).delete()
    time = photo.act.time
    month = time.month
    month_str = list(rus_months.keys())[month - 1]
    date_str = datetime.datetime.strftime(time.astimezone(pytz.timezone('Europe/Moscow')), "%d") + ' ' + month_str
    if date_str[0] == '0':
        date_str = date_str[1:]
    time_str = datetime.datetime.strftime(time.astimezone(pytz.timezone('Europe/Moscow')), "%H%M")
    for num in prefix_concerts:
        path = f"{photo.act.event.group.title}_{photo.act.event.group.sub_title}/{date_str}/{num}_{'_'.join(json.loads(photo.act.groups))}_{time_str}/{photo.name}"
        try:
            client_sync.get_meta(path)
            client_sync.remove(f'watermark/{path}')
            os.remove(f"media/original/{path}")
            os.remove(f"media/watermark/{path}")
            break
        except Exception:
            ...
    act = photo.act
    photo.delete()
    act.photo_counter = act.photos.count()
    act.save()
    PeriodicTask.objects.get(name=f'Удаление фото {photo_id}').delete()


@shared_task(name="delete_file")
def delete_file(**kwargs):
    path = kwargs.get('path')
    try:
        os.remove(path)
    except Exception:
        ...
    PeriodicTask.objects.get(name=f"Удаление файла {path.split('/')[-1]}").delete()


@shared_task(name="email_users")
def email_users(date: datetime.datetime, id, obj):
    if obj == 'мероприятие':
        name = f'Уведомления об удалении мероприятия {id} за 3 дня'
        model = GroupEvent
    elif obj == 'день мероприятия':
        name = f'Уведомления об удалении дня мероприятия {id} за 3 дня'
        model = Event
    elif obj == 'концерт':
        name = f'Уведомления об удалении концерта {id} за 3 дня'
        model = Act
    elif obj == 'фото':
        name = f'Уведомления об удалении фото {id} за 3 дня'
        model = Photo

    PeriodicTask.objects.update_or_create(
        name=name,
        task="email_users",
        interval=IntervalSchedule.objects.get(
            every=1, period='hours'),
        one_off=True,
        defaults={
            'args': json.dumps([id]),
            'start_time': date - datetime.timedelta(days=3),
        }
    )
    if model == GroupEvent:
        photos = Photo.objects.filter(act__event__group_id=id)
    elif model == Event:
        photos = Photo.objects.filter(act__event_id=id)
    elif model == Act:
        photos = Photo.objects.filter(act_id=id)
    elif model == Photo:
        photos = Photo.objects.filter(id=id)

    users_for_mail = set()
    for photo in photos:
        for order in Order.objects.all():
            if photo in order.order_list.all():
                users_for_mail.add(order.user)

    users_for_mail = list(users_for_mail)
    for user in users_for_mail:
        subject = "Удаление фотографий с сайта"
        msg_html = email_photos_remove(user, date.strftime("%d.%m.%Y"))
        user.email_user(subject, message=None, html_message=msg_html)


@shared_task(name="download_originals")
def download_originals(order_id):
    try:
        order = Order.objects.get(order_id=order_id)
        zip_path = f"{PREPEND_PATH}media/download_orders/zips/{order.order_id}.zip"
        folder_path = f"{PREPEND_PATH}media/download_orders/"

        if not os.path.exists(zip_path):
            # Создание ZIP-архива
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for photo in order.order_list.all():
                    file_dir = os.path.join(folder_path, photo.name)
                    download_original_photo(photo.id, file_dir)
                    while not os.path.exists(file_dir):
                        time.sleep(1)

                    zipf.write(file_dir, os.path.relpath(file_dir, folder_path))

            PeriodicTask.objects.update_or_create(
                name=f"Удаление файла {os.path.basename(zip_path)}",
                task='delete_file',
                interval=IntervalSchedule.objects.get(every=15, period='minutes'),
                one_off=True,
                defaults={
                    'kwargs': json.dumps({'path': zip_path}),
                    'start_time': datetime.datetime.now() + datetime.timedelta(hours=24),
                }
            )

        PeriodicTask.objects.filter(name=f"Сохранение файлов заказа {order.order_id}").delete()

    except Exception:
        PrintException()


@shared_task(name="download_original_photo")
def download_original_photo(photo_id, path):
    try:
        photo = Photo.objects.get(id=photo_id)
        act = photo.act
        time = act.time.astimezone(pytz.timezone('Europe/Moscow'))
        month_str = list(rus_months.keys())[time.month - 1]
        date_str = time.strftime("%d") + f" {month_str}"
        time_str = time.strftime("%H%M")

        for num in prefix_concerts:
            path_origin = f"disk:/{act.event.group.title}_{act.event.group.sub_title}/{date_str}/{num}_{'_'.join(json.loads(act.groups))}_{time_str}/{photo.name}"
            try:
                res = client_sync.get_meta(path_origin)
            except Exception:
                if date_str.startswith('0'):
                    date_str = date_str[1:]
                    path_origin = f"disk:/{act.event.group.title}_{act.event.group.sub_title}/{date_str}/{num}_{'_'.join(json.loads(act.groups))}_{time_str}/{photo.name}"
                    res = client_sync.get_meta(path_origin)
                else:
                    continue

            response = requests.get(res['file'], headers=headers)
            image = Image.open(BytesIO(response.content))
            image.save(path, quality=100)

            PeriodicTask.objects.update_or_create(
                name=f"Удаление файла {os.path.basename(path)}",
                task='delete_file',
                interval=IntervalSchedule.objects.get(every=15, period='minutes'),
                one_off=True,
                defaults={
                    'kwargs': json.dumps({'path': path}),
                    'start_time': datetime.datetime.now() + datetime.timedelta(hours=24),
                }
            )
            break

    except Exception:
        PrintException()
