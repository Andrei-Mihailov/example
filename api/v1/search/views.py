import face_recognition
import image_to_numpy
import numpy as np

from keras import preprocessing
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from adrf.decorators import api_view
from django.shortcuts import redirect
from django.http import HttpResponseBadRequest
from datetime import datetime
from pillow_heif import register_heif_opener
from asgiref.sync import sync_to_async

from Catalog.models import Act, Photo, SearchData
from Users.models import Users
from ...utils import PrintException, process_json_request, check_token, PhotoPagination
from ...serializer import ActSerializer, PhotoSerializer, ActInfoSerializer


register_heif_opener()


@api_view(['POST'])
def by_name(request: Request):
    req = process_json_request(request)
    acts = Act.objects.filter(groups__icontains=req['searchString'], visible=True)
    serializer = ActSerializer(acts, many=True)
    return Response(serializer.data)


@sync_to_async
def get_photos(act):
    if act:
        return list(Photo.objects.filter(act=act).only('id', 'metrics'))
    else:
        return list(Photo.objects.all().only('id', 'metrics'))


@sync_to_async
def get_serialized_data(serializer):
    return serializer.data


@sync_to_async
def get_all_data(objects):
    return objects.all()


@api_view(['POST'])
async def search_metrics(request: Request, act_id):
    try:
        # сохраняем юзера
        token = request.COOKIES .get('token', '')
        anonim = False
        if token:
            decode_token = check_token(token)
            if type(decode_token) is Response:
                anonim = True
            else:
                user = await Users.objects.aget(pk=decode_token['id'])
        else:
            anonim = True
        if anonim:
            user, _ = await Users.objects.aget_or_create(
                username='anonimus',
                defaults={
                    'first_name': 'anonimus',
                    'last_name': 'anonimus',
                    'email': 'anonimus',
                    'phone': 'anonimus',
                })
        file = request.FILES.getlist('file_for_send')[0]

        image = image_to_numpy.load_image_file(file)
        # Ищем лица на фото из концерта. Получаем numpy.ndarray
        try:
            # 128-мерная кодировка лица или лиц на фото
            face_numpy_encodings = face_recognition.face_encodings(image)
        except Exception:
            return Response(data='Не удалось определить человека на фото, попробуйте загрузить другую фотографию',
                            status=status.HTTP_400_BAD_REQUEST)
        if len(face_numpy_encodings) == 1:  # все ок
            act = await Act.objects.aget(id=act_id)
            # новый список (для сохранения имен фоток в которых найденно лицо пользователя)
            find_foto_name_list = []
            # поиск совпадений в словаре - концерта
            # Перебираем имена фоток - key. Под ключами лежат массивы с векторами лиц
            tolerance = 0.48
            all_faces_with_photos = []

            for photo in await get_photos(act):
                for face in photo.metrics[0]:
                    if len(face):
                        face_array = np.asarray(face)
                        if face_array.shape[0] == 128:  # Убедимся, что есть 128 признаков
                            all_faces_with_photos.append((face_array, photo))  # Сохраняем кортеж (лицо, фото)

            if all_faces_with_photos:
                # Извлечение лиц и их соответствующих фотографий
                all_faces = [item[0] for item in all_faces_with_photos]
                valid_photos = [item[1] for item in all_faces_with_photos]
                padded_faces = preprocessing.sequence.pad_sequences(all_faces, padding='post', dtype='float32')

                # Выполнение сравнения
                results = face_recognition.compare_faces(
                    [face_numpy_encodings[0]], np.array(padded_faces), tolerance=tolerance)

                find_foto_name_list = []
                for i, result in enumerate(results):
                    if result:
                        if valid_photos[i] not in find_foto_name_list:
                            find_foto_name_list.append(valid_photos[i])

            if find_foto_name_list:
                # сохраняем результат поиска
                search_data = await SearchData.objects.acreate(
                    act=act,
                    user=user,
                    metrics=face_numpy_encodings[0].tolist(),
                    datetime=datetime.now())
                await sync_to_async(search_data.result.set)(find_foto_name_list)
                await sync_to_async(search_data.save)()
                return Response(data={'search_id': search_data.id},
                                status=status.HTTP_200_OK)
            else:
                return Response(data='Поиск не дал результата',
                                status=status.HTTP_400_BAD_REQUEST)

        elif len(face_numpy_encodings) == 0:  # не найдены лица
            return Response(data='Фото пользователя не подходит для поиска: Ни одного лица не найдено',
                            status=status.HTTP_400_BAD_REQUEST)
        else:  # найдено больше 1 лица
            return Response(data='Фото пользователя не подходит для поиска: Более одного человека на фото',
                            status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        PrintException()
        return HttpResponseBadRequest()


@api_view(['GET'])
async def search_by_photo(request: Request, search_id):
    try:
        search_data: SearchData = await SearchData.objects.select_related('act').prefetch_related('result').aget(id=search_id)

        act_info_serializer = ActInfoSerializer(search_data.act)
        paginator = PhotoPagination(p_size=await search_data.result.acount())
        page_photos = paginator.paginate_queryset(await get_all_data(search_data.result), request)
        serializer = PhotoSerializer(page_photos, many=True)
        data = await get_serialized_data(serializer)
        response = paginator.get_paginated_response(data)
        act_info_data = await get_serialized_data(act_info_serializer)
        response.data.update(act_info_data)
        response['X-Total-Count'] = search_data.act.photo_counter
        return response
    except Exception:
        return redirect('/404')
