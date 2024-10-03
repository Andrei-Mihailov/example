from django.urls import path
from . import views as api_views
from . import load as api_load


urlpatterns = [
    path('get_current',
         api_views.get_current, name='get_current'),
    path('add_photo/<photo_id>',
         api_views.add_photo, name='add_photo'),
    path('remove_photo/<photo_id>',
         api_views.remove_photo, name='remove_photo'),
    path('payment_callback',
         api_views.payment_callback, name='payment_callback'),
    path('get_all',
         api_views.get_all, name='get_all'),
    path('get_last',
         api_views.get_last, name='get_last'),
    path('remove_all',
         api_views.remove_all, name='remove_all'),
    path('get_last',
         api_views.get_last, name='get_last'),
    path('add_by_list',
         api_views.add_by_list, name='add_by_list'),
    path('get_by_list',
         api_views.get_by_list, name='get_by_list'),
    path('get_pay_link',
         api_views.get_pay_link, name='get_pay_link'),
]

urlpatterns += [

    path('one/<photo_id>',
         api_load.one, name='one'),
    path('order/<order_id>',
         api_load.order, name='order'),
]
