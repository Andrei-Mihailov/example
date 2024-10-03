import io
import sys
import jwt
import linecache
import json
import datetime
import math

from functools import wraps
from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from termcolor import colored

from Users.models import Users
from Basket.models import Order
from Catalog.models import Photo
from Statistic.models import StatisticUsers


def PrintException():

    _, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f.f_globals)
    print(colored('\tException in file "{}", line {}:\n\t\t "{}": {}'.format(
        filename, lineno, line.strip(), exc_obj), 'red'))
    with open('logs/errors.txt', 'a') as file:
        file.write('Exception in file "{}", line {}:\n\t\t "{}": {}\n'.format(
            filename, lineno, line.strip(), exc_obj))


def JWT_decode(token):
    return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])


class PhotoPagination(PageNumberPagination):
    page_size_query_param = 'limit'
    max_page_size = 100

    def __init__(self, p_size=10):
        self.page_size = p_size


def check_token(token):
    try:
        return JWT_decode(token)
    except jwt.exceptions.ExpiredSignatureError:
        return Response(status=status.HTTP_401_UNAUTHORIZED)
    except jwt.exceptions.InvalidSignatureError:
        return Response(status=status.HTTP_401_UNAUTHORIZED)


def auth_required(func):
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        token = request.COOKIES.get('token', '')
        if func.__name__ == 'get_user_info':
            if not request.COOKIES.get('sessionid', ''):
                update_statistic(new_user=1)
        if token:
            decode_token = check_token(token)
            if type(decode_token) is Response:
                return decode_token
            try:
                user = Users.objects.get(pk=decode_token['id'])
                if user.confirmed:
                    response = func(request, user, *args, **kwargs)
                    return response
            except Exception:
                ...
            return HttpResponseBadRequest()
        return Response(status=status.HTTP_401_UNAUTHORIZED)
    return wrapper


def update_statistic(new_user=0, retried_user=0, registered_user=0):
    if not StatisticUsers.objects.count():
        StatisticUsers.objects.create()
    stat = StatisticUsers.objects.first()
    stat.new_user += new_user
    stat.retried_user += retried_user
    stat.registered_user += registered_user
    stat.save()


def auth_required_async(func):
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        token = request.COOKIES.get('token', '')
        if token:
            decode_token = check_token(token)
            if type(decode_token) is Response:
                return decode_token
            user = await Users.objects.aget(pk=decode_token['id'])
            if user.confirmed:
                return await func(request, user, *args, **kwargs)
            return HttpResponseBadRequest()
        return HttpResponseForbidden()
    return wrapper


def process_json_request(request):
    try:
        stream = io.BytesIO(request.body)
        return JSONParser().parse(stream)
    except Exception:
        return request.data


def change_user(user: Users, phone=None, first_name=None, password=None):
    if phone:
        user.phone = phone
    if first_name:
        user.first_name = first_name
    if password:
        user.set_password(password)
    user.save()

    return user


def get_order_sale(order: Order):
    no_discount_photos = [
        photo for photo in order.order_list.all() if not photo.act.event.group.base_sale]

    if no_discount_photos:
        no_discount_photo_first: Photo = no_discount_photos[0]
        if len(no_discount_photos) >= no_discount_photo_first.act.event.group.sale_price_2_limit:
            order_sale = no_discount_photo_first.act.event.group.sale_price_2
        elif len(no_discount_photos) >= no_discount_photo_first.act.event.group.sale_price_1_limit:
            order_sale = no_discount_photo_first.act.event.group.sale_price_1
        else:
            order_sale = 0
    else:
        order_sale = 0

    order_coast_no_discount = 0
    for photos in no_discount_photos:
        order_coast_no_discount += math.floor(photos.act.event.group.price * (1 - order_sale / 100))
    return order_coast_no_discount, order_sale


def get_order_data(order: Order):
    discount_photos = [
        photo for photo in order.order_list.all() if photo.act.event.group.base_sale]

    order_coast_discount = 0
    for photos in discount_photos:
        order_coast_discount += photos.act.event.group.base_sale

    order_coast = 0
    for photos in order.order_list.all():
        order_coast += photos.act.event.group.price

    order_coast_no_discount, order_sale = get_order_sale(order)
    order.order_sale_coast = order_coast_discount + order_coast_no_discount
    order.order_sale = order_sale
    order.order_coast = order_coast
    order.save()
    return order


def get_photo_price(photo_current: Photo, order: Order):
    no_discount_photos = [
        photo for photo in order.order_list.all() if not photo.act.event.group.base_sale]
    if photo_current in no_discount_photos:
        order_coast_no_discount, _ = get_order_sale(order)
        price = order_coast_no_discount / len(no_discount_photos)
    else:
        price = photo_current.act.event.group.base_sale
    return price


def create_reminder_task(user_id, basket_id):
    PeriodicTask.objects.update_or_create(
        name=f'Напоминание по заказу {basket_id}',
        task='reminder_emails',
        interval=IntervalSchedule.objects.get(
            every=1, period='minutes'),
        one_off=True,
        defaults={
            'kwargs': json.dumps({'user_id': user_id,
                                  'basket_id': basket_id}),
            'start_time': datetime.datetime.now() + datetime.timedelta(days=2)
        }
    )


def modify_photo(user, photo_id, operation):
    from .serializer import OrderSerializer

    try:
        photo = get_object_or_404(Photo, id=photo_id)
        order, _ = Order.objects.get_or_create(user=user, payed=False)

        if operation == 'add':
            order.order_list.add(photo)
            create_reminder_task(user.id, order.id)
        elif operation == 'remove':
            order.order_list.remove(photo)

        order = get_order_data(order)

        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception:
        return HttpResponseForbidden()
