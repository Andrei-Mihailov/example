from .settings import DISK_AUTH_TOKEN
import yadisk


headers = {"Authorization": "OAuth " + DISK_AUTH_TOKEN}

rus_months = {
    'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
    'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
}

prefix_concerts = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"]


client = yadisk.AsyncClient(token=DISK_AUTH_TOKEN)
client_sync = yadisk.Client(token=DISK_AUTH_TOKEN)
