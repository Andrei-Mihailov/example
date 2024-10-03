from rest_framework.request import Request
from rest_framework.response import Response
from adrf.decorators import api_view
from django.shortcuts import redirect
from django.http import HttpResponseNotFound

from Catalog.models import (GroupEvent, Event, Act, Photo)
from ...serializer import (GroupSerializer, EventSerializer,
                           PhotoSerializer, ActInfoSerializer)
from ...utils import PhotoPagination


@api_view(['GET'])
def get_all(request: Request):
    group = GroupEvent.objects.filter(visible=True)
    serializer = GroupSerializer(group, many=True)
    response = Response(serializer.data)
    return response


@api_view(['GET'])
def get_event_by_group(request: Request, group_id):
    event = Event.objects.filter(group=group_id, visible=True)
    if event.exists():
        serializer = EventSerializer(event, many=True)
        return Response(serializer.data)
    return HttpResponseNotFound()


@api_view(['GET'])
def get_event(request: Request, event_id):
    event = Event.objects.get(id=event_id, visible=True)
    serializer = EventSerializer(event)
    return Response(serializer.data)


@api_view(['GET'])
def get_concert(request: Request, act_id):
    act = Act.objects.filter(id=act_id, visible=True)
    if act.exists():
        act = act.first()
        photos = Photo.objects.select_related('act__event').filter(act__id=act_id)
        paginator = PhotoPagination()
        page_photos = paginator.paginate_queryset(photos, request)

        serializer = PhotoSerializer(page_photos, many=True)
        act_info_serializer = ActInfoSerializer(act)
        response = paginator.get_paginated_response(serializer.data)
        response.data.update(act_info_serializer.data)
        response['X-Total-Count'] = act.photo_counter
        return response
    else:
        return redirect('/404')


@api_view(['GET'])
def get_photo_info(request: Request, photo_id):
    photo = Photo.objects.select_related('act').get(id=photo_id)
    photo_index = Photo.objects.filter(act=photo.act).filter(id__lt=photo.id).count()
    page_number = (photo_index // 48) + 1
    return Response(data={
        "act_id": photo.act.id,
        "page_number": page_number
    })
