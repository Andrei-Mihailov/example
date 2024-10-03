from django.urls import path
from . import views as api_views

urlpatterns = [
    path('by_name',
         api_views.by_name, name='by_name'),
    path('search_metrics/<act_id>',
         api_views.search_metrics, name='search_metrics'),
    path('search_by_photo/<search_id>',
         api_views.search_by_photo, name='search_by_photo'),
]
