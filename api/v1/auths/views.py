import json

from adrf.decorators import api_view
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.exceptions import APIException
from django.http import HttpResponseRedirect
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

from .utils import YandexOAuth, VKOAuth

ya_oauth = YandexOAuth()
vk_oauth = VKOAuth()


@csrf_exempt
def get_csrf_token(request: Request):
    csrf_token = get_token(request)
    return JsonResponse({'csrfToken': csrf_token})


@api_view(['GET'])
async def auth_yandex(request: Request):
    response = Response(await ya_oauth.get_authorize_url(), status=status.HTTP_303_SEE_OTHER)
    return response


@api_view(['GET'])
async def yandex_code(request: Request):
    code = request.query_params.get('code')
    login_result = await ya_oauth.register(
        code=code
    )
    if login_result == status.HTTP_409_CONFLICT:
        raise APIException(
            status_code=status.HTTP_409_CONFLICT,
            detail='User not found'
        )

    if login_result == status.HTTP_401_UNAUTHORIZED:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid password'
        )
    if not login_result:
        raise APIException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Can't login"
        )
    response = HttpResponseRedirect('/')
    token = login_result.token
    response.set_cookie("token", token)
    return response


@api_view(['GET'])
async def auth_vk(request: Request):
    response = Response(await vk_oauth.get_authorize_url(), status=status.HTTP_303_SEE_OTHER)
    return response


@api_view(['GET'])
async def auth_vk_webhook(request: Request):
    payload = json.loads(request.query_params.get('payload'))
    login_result = await vk_oauth.register(
        payload=payload
    )

    if login_result == status.HTTP_409_CONFLICT:
        raise APIException(
            status_code=status.HTTP_409_CONFLICT,
            detail='User not found'
        )

    if login_result == status.HTTP_401_UNAUTHORIZED:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid password'
        )
    if not login_result:
        raise APIException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Can't login"
        )
    response = HttpResponseRedirect('/')
    token = login_result.token
    response.set_cookie("token", token)
    return response
