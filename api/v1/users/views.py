import datetime
import json

from pytz import timezone
from adrf.decorators import api_view
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth import login, logout
from django.http import HttpResponseForbidden, HttpResponseBadRequest

from Users.models import Users, CallbackUrls
from Emails.models import Contact, Emails
from ...serializer import UsersSerializer
from ...utils import auth_required, change_user, process_json_request, update_statistic
from ...emails import email_confirm, email_change_password, email_data_changed, email_feedback


def get_user(phone, email, name, password, email_notifications):
    username = name + '_' + email
    user, created = Users.objects.get_or_create(
        email=email,
        defaults={
            'phone': phone,
            'first_name': name,
            'username': username,
            'email_notifications': email_notifications.lower() == 'true'
        })
    if created:
        user.set_password(password)
        user.save()
        call_user = CallbackUrls.objects.create(user=user)
        subject = "Подтверждение почты"
        msg_html = email_confirm(call_user)
        user.email_user(subject, message=None, html_message=msg_html)
    return user, created


@api_view(['POST'])
def user_registration(request: Request):
    req = process_json_request(request)

    user, created = get_user(req['user']['phone'],
                             req['user']['email'],
                             req['user']['name'],
                             req['user']['password'],
                             req['user']['confirm_ads'])
    if created:
        serializer = UsersSerializer(user)
        response = Response(serializer.data, status=status.HTTP_201_CREATED)
    else:
        response = Response(status=status.HTTP_409_CONFLICT)
    return response


@api_view(['GET'])
def confirm_email(request: Request, confirm_uuid):
    call_user = CallbackUrls.objects.filter(uuid=confirm_uuid)
    if call_user.exists():
        call_user = call_user.first()
        if (call_user.expired > datetime.datetime.now(tz=timezone('UTC'))
                and call_user.type_url == CallbackUrls.UrlType.CONFIRM):
            user = call_user.user
            user.confirmed = True
            user.save()
            call_user.delete()
            update_statistic(registered_user=1)
            return redirect('/user_confirm')
        return HttpResponseBadRequest()
    else:
        return redirect('/link_fail')


@api_view(['POST'])
def login_user(request: Request):
    req = process_json_request(request)
    try:
        email = req["email"]
        password = req["password"]
        user = Users.objects.get(email=email)
        if user.confirmed:
            if user.check_password(password):
                login(request, user)
                token = user.token
                response = Response(status=status.HTTP_200_OK)
                response.set_cookie("token", token, samesite='None', secure=True)
                update_statistic(retried_user=1)
                return response
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        return Response(status=status.HTTP_403_FORBIDDEN)
    except Exception:
        return HttpResponseBadRequest()


@api_view(['POST'])
@auth_required
def logout_user(request: Request, user: Users):
    try:
        logout(request)
        response = Response(status=200)
        response.delete_cookie("token")
        return response
    except Exception:
        return Response(status=status.HTTP_401_UNAUTHORIZED)


@api_view(['PATCH'])
@auth_required
def change_data_user(request: Request, user: Users):
    try:
        req = process_json_request(request)
        phone = None
        password = None
        first_name = None
        if 'phone' in req:
            phone = req['phone']
        if 'password' in req:
            password = req['password']
        if 'name' in req:
            first_name = req['name']
        user = change_user(user, phone, first_name, password)
        serializer = UsersSerializer(user)
        response = Response(
            serializer.data, status=status.HTTP_200_OK)
        subject = "Изменение личных данных"
        msg_html = email_data_changed(user)
        user.email_user(subject, message=None, html_message=msg_html)
        return response
    except Exception:
        return HttpResponseForbidden()


@api_view(['POST'])
def change_password_user(request: Request):
    req = process_json_request(request)
    email = req['email']
    try:
        user = Users.objects.get(email=email)
        if user and user.confirmed:
            call_user = CallbackUrls.objects.create(
                user=user, type_url=CallbackUrls.UrlType.PASS_RESET)

            subject = f"Восстановление пароля на {settings.ALLOWED_HOSTS[0]}"
            msg_html = email_change_password(call_user)
            user.email_user(subject, message=None, html_message=msg_html)
            response = Response(status=status.HTTP_204_NO_CONTENT)
            return response
        return Response(status=status.HTTP_404_NOT_FOUND)
    except Exception:
        return HttpResponseForbidden()


@api_view(['POST'])
def change_password_confirm(request: Request, confirm_uuid):
    req = process_json_request(request)
    password = req['password']
    call_user = get_object_or_404(CallbackUrls, uuid=confirm_uuid)
    if (call_user.expired > datetime.datetime.now(tz=timezone('UTC'))
            and call_user.type_url == CallbackUrls.UrlType.PASS_RESET):
        user = call_user.user
        if user and user.confirmed:
            user = change_user(user, password=password)
            call_user.delete()
            serializer = UsersSerializer(user)
            response = Response(serializer.data, status=status.HTTP_200_OK)
            subject = "Изменение личных данных"
            msg_html = email_data_changed(user)
            user.email_user(subject, message=None, html_message=msg_html)
            return response
    return Response(status=status.HTTP_401_UNAUTHORIZED)


@api_view(['GET'])
@auth_required
def get_user_info(request: Request, user: Users):
    try:
        serializer = UsersSerializer(user)
        response = Response(serializer.data, status=status.HTTP_200_OK)
        return response
    except Exception:
        return HttpResponseForbidden()


@api_view(['POST'])
def feedback(request: Request):
    req = process_json_request(request)
    try:
        email = req["email"]
        phone = req["phone"]
        name = req["name"]
        message = req['message']

        support = Contact.objects.first()
        user, _ = Contact.objects.get_or_create(
            email=email,
            defaults={
                'phone': phone,
                'first_name': name,
            })
        Emails.objects.create(sender=user,
                              receiver=support,
                              message=message)
        subject = "Обратная связь"
        msg_html = email_feedback(user)
        user.email_user(subject, message=None, html_message=msg_html)
        return Response(status=status.HTTP_200_OK)
    except Exception:
        return HttpResponseForbidden()


@api_view(['POST'])
@auth_required
def set_custom_option(request: Request, user: Users):
    req = process_json_request(request)
    try:
        jsonObj = req["jsonObj"]
        if jsonObj:
            user.custom_options = json.loads(jsonObj)
        else:
            user.custom_options = {}
        user.save()
        return Response(status=status.HTTP_200_OK)
    except Exception:
        return HttpResponseForbidden()
