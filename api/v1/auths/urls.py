from django.urls import path
from . import views as api_views

urlpatterns = [
    path('yandex',
         api_views.auth_yandex, name='auth_yandex'),
    path('yandex_code',
         api_views.yandex_code, name='yandex_code'),
    path('vk',
         api_views.auth_vk, name='auth_vk'),
    path('auth_vk_webhook',
         api_views.auth_vk_webhook, name='auth_vk_webhook'),
    path('get_csrf_token', api_views.get_csrf_token, name="dispatch")
]
