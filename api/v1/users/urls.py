from django.urls import path
from . import views as api_views

urlpatterns = [
    path('registration',
         api_views.user_registration, name='registration'),
    path('confirm/<str:confirm_uuid>',
         api_views.confirm_email, name='confirm_email'),
    path('login',
         api_views.login_user, name='login'),
    path('logout',
         api_views.logout_user, name='logout'),
    path('get_user_info',
         api_views.get_user_info, name='get_user_info'),
    path('change',
         api_views.change_data_user, name='change'),
    path('change_password',
         api_views.change_password_user, name='change_password'),
    path('change_password_confirm/<str:confirm_uuid>',
         api_views.change_password_confirm, name='change_password_confirm'),
    path('feedback',
         api_views.feedback, name='feedback'),
    path('set_custom_option',
         api_views.set_custom_option, name='set_custom_option'),
]
