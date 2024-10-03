from django.urls import path
from . import views as api_views

urlpatterns = [
    path('get_all',
         api_views.get_all, name='get_all'),
    path('get_event_by_group/<group_id>',
         api_views.get_event_by_group, name='get_event_by_group'),
    path('get_event/<event_id>',
         api_views.get_event, name='get_event'),
    path('get_concert/<act_id>',
         api_views.get_concert, name='get_concert'),
    path('get_photo_info/<photo_id>',
         api_views.get_photo_info, name='get_photo_info')
]
