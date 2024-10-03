from django.urls import path, include

urlpatterns = [
    path('catalog/', include('api.v1.catalog.urls')),
    path('users/', include('api.v1.users.urls')),
    path('order/', include('api.v1.basket.urls')),
    path('download/', include('api.v1.basket.urls')),
    path('auth/', include('api.v1.auths.urls')),
    path('search/', include('api.v1.search.urls'))
]
