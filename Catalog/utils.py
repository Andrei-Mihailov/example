import datetime
import json
import os
import requests
import pytz
import yadisk

from io import BytesIO
from PIL import Image

from .models import GroupEvent, Event, Act, Photo
from Mydance.config import headers, rus_months, prefix_concerts, client_sync


class DataMigrator:
    def __init__(self, state_file="logs/state.json"):
        self.state_file = state_file

    def load_state(self):
        """
        Загружает состояние из файла.
        """
        state = {"offset": 0}
        if os.path.exists(self.state_file):
            with open(self.state_file, "r") as f:
                state = json.load(f)
        return state

    def save_state(self, state):
        """
        Сохраняет состояние в файл.
        """
        with open(self.state_file, "w") as f:
            json.dump(state, f)


def format_path(path):
    date_str = path.split("/")[1].strip()
    year_str = path.split("_")[1].split("/")[0].split(" ")[1]
    day, month = date_str.split(" ")
    month_num = rus_months[month]
    event_title, event_sub_title = path.split('/')[0].split('_')
    event_date = datetime.datetime(int(year_str), month_num, int(day))
    act_groups = json.dumps(path.split(
        "/")[-1].split('_')[1:-1], ensure_ascii=False)
    act_time = path.split("/")[-1].split('_')[-1]
    act_time = act_time[:2] + ':' + act_time[2:]
    act_time = datetime.datetime.combine(date=event_date.date(),
                                         time=datetime.datetime.strptime(act_time, '%H:%M').time())
    return event_title, event_sub_title, event_date, act_groups, act_time


def get_or_create_group_event(event_title, event_sub_title):
    event, event_created = GroupEvent.objects.get_or_create(
        title=event_title,
        sub_title=event_sub_title)
    return event, event_created


def get_or_create_event(event_date, group):
    event, event_created = Event.objects.get_or_create(date=event_date,
                                                       group=group)
    return event, event_created


def get_or_create_act(event, act_time, act_groups):
    act, act_created = Act.objects.get_or_create(
        event=event,
        time=act_time,
        groups=act_groups)
    return act, act_created


def get_or_create_photo(act, preview_url, preview_watermark_url, file, orient, metrics):
    photo, photo_created = Photo.objects.get_or_create(
        preview_url=preview_url,
        preview_watermark_url=preview_watermark_url,
        original_url=file['file'],
        photo_orient=orient,
        name=file['name'],
        metrics=metrics,
        act=act
    )
    return photo, photo_created


def get_image(input_image_url):
    with requests.Session() as session:
        response = session.get(input_image_url, headers=headers)
        image = Image.open(BytesIO(response.content))
        if image.size[0] > image.size[1]:  # горизонтальная ориентация
            new_image_url = input_image_url.replace(
                'size=S', 'size=700x467')
            watermark = Image.open('mini gorizont.png').convert('RGBA')
        else:
            new_image_url = input_image_url.replace(
                'size=S', 'size=467x700')
            watermark = Image.open('mini vertical.png').convert('RGBA')

        response = session.get(new_image_url, headers=headers)
        base_image = Image.open(BytesIO(response.content))
    return image, base_image, watermark, new_image_url


def watermark_photo(input_image_url,
                    output_image_path):
    try:
        image, base_image, watermark, new_image_url = get_image(input_image_url)

        transparent = Image.new('RGBA', base_image.size)
        transparent.paste(base_image, (0, 0))
        transparent.paste(watermark, (0, 0),
                          mask=watermark)
        image_stream = BytesIO()
        transparent.save(image_stream, format='PNG')
        image_stream.seek(0)
        try:
            client_sync.upload(image_stream, output_image_path, n_retries=5,
                               retry_interval=2, timeout=5, overwrite=True)
        except yadisk.exceptions.PathExistsError:
            ...
        except Exception as e:
            print(e)
            return watermark_photo(input_image_url,
                                   output_image_path)
        # вертикальная ориентация = 1, горизонтальная = 0
        return image.size[0] < image.size[1], new_image_url
    except Exception as e:
        print("Ошибка при обработке фото: " +
              output_image_path.replace('disk:/watermark/', ''))
        print(e)
        return watermark_photo(input_image_url,
                               output_image_path)


def save_previews_to_disk(photo: Photo):
    act: Act = photo.act
    time = act.time
    month = time.month
    month_str = list(rus_months.keys())[month - 1]
    date_str = datetime.datetime.strftime(time.astimezone(pytz.timezone('Europe/Moscow')), "%d") + ' ' + month_str
    time_str = datetime.datetime.strftime(time.astimezone(pytz.timezone('Europe/Moscow')), "%H%M")
    path_watermark = f"media/watermark/{act.event.group.title}_{act.event.group.sub_title}/{date_str}/{'_'.join(json.loads(act.groups))}_{time_str}"
    path = path_watermark.replace('watermark', 'original')
    if not os.path.exists(path_watermark):
        os.makedirs(path_watermark)
    if not os.path.exists(path):
        os.makedirs(path)

    try:
        response_watermark = requests.get(photo.preview_watermark_url, headers=headers)
        image_watermark = Image.open(BytesIO(response_watermark.content))
        image_watermark.save(f"{path_watermark}/{photo.name}")
        photo.preview_watermark_url_host = f"{path_watermark}/{photo.name}"
    except Exception:
        for num in prefix_concerts:
            path_temp = f"disk:/watermark/{act.event.group.title}_{act.event.group.sub_title}/{date_str}/{num}_{'_'.join(json.loads(act.groups))}_{time_str}/{photo.name}"
            try:
                res = client_sync.get_meta(path_temp)
                if photo.photo_orient:
                    preview_watermark_url = res['preview'].replace(
                        'size=S', 'size=467x700')
                else:
                    preview_watermark_url = res['preview'].replace(
                        'size=S', 'size=700x467')
                photo.preview_watermark_url = preview_watermark_url
                response_watermark = requests.get(preview_watermark_url, headers=headers)
                image_watermark = Image.open(BytesIO(response_watermark.content))
                image_watermark.save(f"{path_watermark}/{photo.name}")
                photo.preview_watermark_url_host = f"{path_watermark}/{photo.name}"
                break
            except Exception:
                ...
    response = requests.get(photo.preview_url, headers=headers)
    image = Image.open(BytesIO(response.content))
    image.save(f"{path}/{photo.name}")
    photo.preview_url_host = f"{path}/{photo.name}"
    photo.save()
    return photo


def remove_dir(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            os.remove(file_path)
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            try:
                os.rmdir(dir_path)
            except Exception:
                remove_dir(dir_path)
    os.rmdir(directory)
