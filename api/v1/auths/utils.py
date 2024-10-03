import string
import httpx
import uuid
import json

from secrets import choice as secrets_choice
from http import HTTPStatus
from django.conf import settings
from asgiref.sync import sync_to_async

from Users.models import SocialAccount, Users


def generate_random_string():
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets_choice(alphabet) for _ in range(16))


class YandexOAuth:
    def __init__(self):
        super().__init__()
        self.client_id = settings.YA_CLIENT_ID
        self.client_secret = settings.YA_CLIENT_SECRET
        self.oauth_url = settings.YA_OAUTH_URL
        self.login_url = settings.YA_LOGIN_URL
        self.model = SocialAccount

    async def get_authorize_url(self) -> str:
        authorize_url = f"{self.oauth_url}authorize?response_type=code&client_id={self.client_id}"
        return authorize_url

    async def register(self, code):
        data_token = await self.get_token(code)
        social_user = await self.get_user_info(data_token['access_token'])

        username = social_user['first_name'] + '_' + \
            social_user['default_phone']['number']
        user, _ = await sync_to_async(Users.objects.get_or_create)(
            email=social_user['default_email'],
            defaults={
                'confirmed': True,
                'phone': social_user['default_phone']['number'],
                'first_name': social_user['first_name'],
                'username': username,
            })
        account, _ = await sync_to_async(SocialAccount.objects.get_or_create)(
            social_id=social_user['psuid'],
            social_name='yandex',
            defaults={
                'user': user,
                'social_id': social_user['psuid'],
                'social_name': 'yandex',
            })

        return user

    async def get_token(self, code: str) -> dict:
        """Обмен кода подтверждения на токен."""
        url = self.oauth_url + "token"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        payload = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=payload, headers=headers)
        data = None

        if response.status_code == HTTPStatus.BAD_REQUEST:
            data = response.json()
            data['authorize_url'] = await self.get_authorize_url()

        if response.status_code == HTTPStatus.OK:
            data = response.json()

        return data

    async def get_user_info(self, access_token) -> dict:
        """Запрос информации о пользователе."""
        url = self.login_url + 'info'
        headers = {
            'Authorization': f'OAuth {access_token}',
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)

        data = None

        if response.status_code == HTTPStatus.BAD_REQUEST:
            data = response.json()

        if response.status_code == HTTPStatus.OK:
            data = response.json()

        return data


class VKOAuth:
    def __init__(self):
        super().__init__()
        self.app_id = settings.VK_APP_ID
        self.redirect_url = settings.VK_REDIRECT_URL
        self.service_token = settings.VK_SERVICE_TOKEN
        self.model = SocialAccount

    async def get_authorize_url(self) -> str:
        uuid_user = uuid.uuid4()
        auth_link = f"https://id.vk.com/auth?uuid={uuid_user}&app_id={self.app_id}&response_type=silent_token&redirect_uri={self.redirect_url}"
        return auth_link

    async def register(self, payload: dict):
        data_token = await self.get_token(payload)
        social_user = await self.get_user_info(payload, data_token)

        username = social_user['first_name'] + '_' + social_user['phone']
        user, created = await sync_to_async(Users.objects.get_or_create)(
            email=social_user['email'],
            defaults={
                'confirmed': True,
                'phone': social_user['phone'],
                'first_name': social_user['first_name'],
                'username': username,
            })
        account, created_social = await sync_to_async(SocialAccount.objects.get_or_create)(
            social_id=social_user['id'],
            social_name='vk',
            defaults={
                'user': user,
                'social_id': social_user['id'],
                'social_name': 'vk',
            })

        return user

    async def get_token(self, payload: dict) -> dict:
        """Обмен токена"""
        url = "https://api.vk.com/method/auth.exchangeSilentAuthToken"
        payload_new = {
            "v": "5.131",
            "token": payload['token'],
            "access_token": self.service_token,
            "uuid": payload["uuid"]
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=payload_new)

        return json.loads(response.text)

    async def get_user_info(self, payload: dict, data_token: dict) -> dict:
        """Информация о пользователе."""
        user = payload['user']
        user['phone'] = '+' + data_token['response']['phone']
        user['email'] = data_token['response']['email']
        return user
