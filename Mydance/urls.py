from django.shortcuts import redirect
from django.urls import path, include, re_path
from django.conf.urls.static import static
from django.contrib import admin
from django.views.generic import TemplateView

from . import settings

urlpatterns = [
    path('', TemplateView.as_view(template_name='index.html')),
    path('favicon.ico', lambda _: redirect('static/favicon.ico', permanent=True)),
    path('api/', include('api.urls')),
    path('0bb49f71-7ea2-4cf2-aa83-b6e959a7a440/', admin.site.urls),
    path('statistic/', include('Statistic.urls'))
]

urlpatterns += static(settings.STATIC_URL)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns.append(re_path(r'^.*$', TemplateView.as_view(template_name='index.html')))
