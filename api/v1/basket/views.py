import datetime
import json

from pytz import timezone
from rest_framework.decorators import api_view, authentication_classes
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from django.http import HttpResponseForbidden, HttpResponseNotFound, HttpResponseServerError, HttpResponseBadRequest
from rest_framework.authentication import SessionAuthentication
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from django.db.models import Max

from Users.models import Users
from Basket.models import Order, Purchase
from Catalog.models import Photo
from ...serializer import OrderSerializer, OrderPayedSerializer
from ...utils import auth_required, modify_photo, process_json_request, get_order_data, get_photo_price, create_reminder_task
from ...emails import email_paymend_accept, email_order_links
from ...robokassa import generate_payment_link, check_success_payment


class CsrfExemptSessionAuthentication(SessionAuthentication):

    def enforce_csrf(self, request):
        return


def ignore_csrf(view_func):
    return authentication_classes([CsrfExemptSessionAuthentication])(view_func)


@api_view(['POST'])
@ignore_csrf
def payment_callback(request: Request):
    try:
        if check_success_payment(request):
            param_request = request.POST
            order_id = param_request['InvId']
            order: Order = Order.objects.get(order_id=order_id)
            if not order.payed:
                order.payed = True
                order.payed_date = datetime.datetime.now()
                order.expired = None
                order.save()
                user: Users = order.user
                subject = "Уведомление об оплате заказа"
                msg_html = email_paymend_accept(user)
                user.email_user(subject, message=None, html_message=msg_html)

                subject = f"Заказ номер {order_id}"
                msg_html_1 = email_order_links(user, order)
                user.email_user(subject, message=None, html_message=msg_html_1)

                PeriodicTask.objects.get(name=f'Напоминание по заказу {order.id}').delete()
            return Response(status=status.HTTP_200_OK)
        return HttpResponseBadRequest()
    except Exception:
        return HttpResponseForbidden()


@api_view(['GET'])
@auth_required
def get_current(request: Request, user: Users):
    try:
        order = Order.objects.filter(user=user, payed=False)
        if order.exists():
            order = order.first()
            if order.expired < datetime.datetime.now(tz=timezone('UTC')):
                order.delete()
            else:
                serializer = OrderSerializer(order)
                return Response(
                    serializer.data, status=status.HTTP_200_OK)
        return HttpResponseNotFound()
    except Exception:
        return HttpResponseForbidden()


@api_view(['GET'])
@auth_required
def get_all(request: Request, user):
    try:
        order_current = Order.objects.filter(user=user,
                                             payed=False)
        orders_old = Order.objects.filter(user=user,
                                          payed=True)
        if order_current.exists():
            serializer = OrderSerializer(order_current.first())
        serializer_old = OrderPayedSerializer(orders_old, many=True)
        return Response({'current_order': serializer.data if order_current.exists() else None,
                        'previos_order': serializer_old.data},
                        status=status.HTTP_200_OK)
    except Exception:
        return HttpResponseServerError()


@api_view(['GET'])
@auth_required
def get_last(request: Request, user):
    try:
        orders_last = Order.objects.filter(user=user,
                                           payed=True).last()
        serializer = OrderPayedSerializer(orders_last)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception:
        return HttpResponseServerError()


@api_view(['DELETE'])
@auth_required
def remove_all(request: Request, user):
    try:
        Order.objects.filter(user=user,
                             payed=False).delete()
        return Response(status=status.HTTP_200_OK)
    except Exception:
        return HttpResponseServerError()


@api_view(['POST'])
@auth_required
def add_photo(request: Request, user: Users, photo_id):
    return modify_photo(user, photo_id, 'add')


@api_view(['DELETE'])
@auth_required
def remove_photo(request: Request, user: Users, photo_id):
    return modify_photo(user, photo_id, 'remove')


@api_view(['POST'])
@auth_required
def add_by_list(request: Request, user: Users):
    req = process_json_request(request)
    photos_queryset = Photo.objects.filter(id__in=req['data'])
    order, _ = Order.objects.get_or_create(user=user, payed=False)
    for photo in photos_queryset:
        order.order_list.add(photo)
    serializer = OrderSerializer(order)
    create_reminder_task(user.id, order.id)
    return Response(
        serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
def get_by_list(request: Request):
    req = process_json_request(request)
    photos_queryset = Photo.objects.filter(id__in=req['data'])
    order = Order.objects.create()
    for photo in photos_queryset:
        order.order_list.add(photo)
    order = get_order_data(order)
    serializer = OrderSerializer(order)
    order_data = serializer.data
    order.delete()
    return Response(order_data, status=status.HTTP_200_OK)


@api_view(['GET'])
@auth_required
def get_pay_link(request: Request, user):
    order = Order.objects.get(user=user, payed=False)
    for photo in order.order_list.all():
        Purchase.objects.update_or_create(
            order=order,
            photo=photo,
            defaults={
                'user': user,
                'purchase_price': round(get_photo_price(photo, order), 2),
            }
        )
    if not order.order_id:
        max_order_id = Order.objects.filter(order_id__isnull=False).aggregate(Max('order_id'))
        order.order_id = max_order_id['order_id__max'] + 1
        try:
            order.save()
        except Exception as e:
            if "Duplicate entry" in str(e):
                try:
                    while True:
                        max_order_id = Order.objects.filter(order_id__isnull=False).aggregate(Max('order_id'))
                        order.order_id = max_order_id['order_id__max'] + 1
                        order.save()
                        break
                except Exception:
                    ...
            else:
                return HttpResponseBadRequest()

    link = generate_payment_link(cost=order.order_sale_coast,
                                 number=order.order_id,
                                 order=order)
    PeriodicTask.objects.update_or_create(
        name=f"Сохранение файлов заказа {order.order_id}",
        task='download_originals',
        interval=IntervalSchedule.objects.get(
            every=15, period='minutes'),
        one_off=True,
        defaults={
            'args': json.dumps([order.order_id]),
            'start_time': datetime.datetime.now(),
        }
    )
    return Response(link, status=status.HTTP_200_OK)
