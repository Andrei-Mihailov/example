import os
import asyncio

from adrf.decorators import api_view
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from django_celery_beat.models import PeriodicTask

from Mydance.settings import PREPEND_PATH
from Users.models import Users
from Basket.models import Order, Purchase
from Catalog.models import Photo
from Catalog.tasks import download_original_photo, download_originals
from ...utils import auth_required_async


@api_view(['GET'])
@auth_required_async
async def one(request: Request, user: Users, photo_id):
    try:
        photo = await Photo.objects.aget(id=photo_id)
        purchase = await Purchase.objects.select_related('order').aget(user=user, photo=photo)
        if purchase.order.payed:
            file_dir = f"{PREPEND_PATH}media/download_orders/{photo.name}"
            if not os.path.exists(file_dir):
                download_original_photo.delay(photo.id, file_dir)
            while not os.path.exists(file_dir):
                await asyncio.sleep(1)
            return Response(file_dir.replace(PREPEND_PATH, ''),
                            status=status.HTTP_200_OK)
        return Response(status=status.HTTP_403_FORBIDDEN)
    except Photo.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    except Purchase.DoesNotExist:
        return Response(status=status.HTTP_403_FORBIDDEN)
    except Exception:
        return Response(status=status.HTTP_403_FORBIDDEN)


@ api_view(['GET'])
@ auth_required_async
async def order(request: Request, user: Users, order_id):
    try:
        order = await Order.objects.aget(order_id=order_id)
        if await Purchase.objects.filter(user=user, order_id=order.id).afirst():
            if order.payed:
                zip_path = f"{PREPEND_PATH}media/download_orders/zips/{order_id}.zip"
                if not os.path.exists(zip_path):
                    download_originals.delay(order_id)
                while True:
                    if await PeriodicTask.objects.filter(name=f"Удаление файла {zip_path.split('/')[-1]}").aexists():
                        break
                    await asyncio.sleep(1)
                return Response(zip_path.replace(PREPEND_PATH, ''),
                                status=status.HTTP_200_OK)
            return Response(status=status.HTTP_403_FORBIDDEN)
        return Response(status=status.HTTP_404_NOT_FOUND)
    except Order.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    except Purchase.DoesNotExist:
        return Response(status=status.HTTP_403_FORBIDDEN)
    except Exception:
        return Response(status=status.HTTP_403_FORBIDDEN)
