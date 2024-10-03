import json
import math

from rest_framework import serializers

from Catalog.models import GroupEvent, Event, Act, Photo, ColorsEvent
from Users.models import Users
from Basket.models import Order, Purchase
from .utils import get_order_sale, get_order_data


class ActSerializer(serializers.ModelSerializer):
    act_id = serializers.SerializerMethodField()
    groups = serializers.SerializerMethodField()

    class Meta:
        model = Act
        fields = ['act_id', 'time', 'groups', 'photo_counter']

    def get_act_id(self, instance):
        return instance.id

    def get_groups(self, instance):
        return json.loads(instance.groups)


class AllGroupSerializer(serializers.ModelSerializer):
    event_id = serializers.SerializerMethodField()

    class Meta:
        model = GroupEvent
        fields = ['date', 'title', 'sub_title',
                  'image_url', 'group', 'event_id', 'price', 'base_sale']

    def get_event_id(self, instance):
        return instance.id


class GroupSerializer(serializers.ModelSerializer):
    date = serializers.SerializerMethodField()
    color_main = serializers.SerializerMethodField()

    class Meta:
        model = GroupEvent
        fields = ['id', 'date', 'title', 'sub_title', 'color_main', 'image_url', 'price', 'base_sale']

    def get_date(self, instance):
        return instance.event.first().date

    def get_color_main(self, instance):
        return map(int, ColorsEvent.objects.get(group_event_id=instance.id).color_main.split(','))


class EventSerializer(serializers.ModelSerializer):
    acts = ActSerializer(many=True, read_only=True)
    title = serializers.SerializerMethodField()
    subtitle = serializers.SerializerMethodField()
    color_main = serializers.SerializerMethodField()
    color_start = serializers.SerializerMethodField()
    color_end = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = ['title', 'subtitle', 'date', 'image_url', 'color_main', 'color_start', 'color_end', 'acts']

    def get_title(self, instance: Event):
        return instance.group.title

    def get_subtitle(self, instance: Event):
        return instance.group.sub_title

    def get_color_main(self, instance: Event):
        return map(int, ColorsEvent.objects.get(group_event_id=instance.group.id).color_main.split(','))

    def get_color_start(self, instance: Event):
        return map(int, ColorsEvent.objects.get(group_event_id=instance.group.id).color_start.split(','))

    def get_color_end(self, instance: Event):
        return map(int, ColorsEvent.objects.get(group_event_id=instance.group.id).color_end.split(','))


class PhotoSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source='act.event.group.title')
    sub_title = serializers.CharField(source='act.event.group.sub_title')
    group_id = serializers.CharField(source='act.event.group.id')
    photo_id = serializers.SerializerMethodField()
    photo_coast = serializers.SerializerMethodField()
    photo_sale_coast = serializers.SerializerMethodField()
    preview_watermark_url = serializers.SerializerMethodField()
    photo_sale_order_coast = serializers.SerializerMethodField()

    class Meta:
        model = Photo
        fields = [
            'title',
            'sub_title',
            'group_id',
            'preview_watermark_url',
            'photo_orient',
            'photo_id',
            'photo_coast',
            'photo_sale_coast',
            'photo_sale_order_coast',
            'deleted_at'
        ]

    def get_photo_id(self, instance):
        return instance.id

    def get_photo_coast(self, obj: Photo):
        return obj.act.event.group.price

    def get_photo_sale_coast(self, obj: Photo):
        return obj.act.event.group.base_sale

    def get_photo_sale_order_coast(self, obj: Photo):
        try:
            if not obj.act.event.group.base_sale:
                order: Order = self.parent.parent.instance
                _, order_sale = get_order_sale(order)
                if order_sale:
                    return math.floor(obj.act.event.group.price * (1 - order_sale / 100))
            return None
        except Exception:
            return None

    def get_preview_watermark_url(self, obj: Photo):
        return obj.preview_watermark_url_host


class ActInfoSerializer(serializers.Serializer):
    time = serializers.DateTimeField()
    groups = serializers.SerializerMethodField()
    title = serializers.CharField(source='event.group.title')
    sub_title = serializers.CharField(source='event.group.sub_title')

    def get_groups(self, instance):
        return json.loads(instance.groups)


class UsersSerializer(serializers.ModelSerializer):
    class Meta:
        model = Users
        fields = ['id', 'first_name', 'phone', 'email', 'confirmed', 'custom_options']


class UserCartSerializer(serializers.Serializer):
    user = UsersSerializer()
    user_cart = PhotoSerializer(source='order_list', many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['user', 'user_cart']

    def get_user_cart(self, obj):
        return PhotoSerializer(obj.first().order_list.all(), many=True, read_only=True)


class OrderSerializer(serializers.ModelSerializer):
    order_list = PhotoSerializer(many=True, read_only=True)
    order_sale_coast = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['order_id', 'order_coast', 'order_sale',
                  'order_sale_coast', 'order_list', 'updated_at']

    def get_order_sale_coast(self, obj):
        get_order_data(obj)
        return obj.order_sale_coast

    def get_updated_at(self, obj: Order):
        return obj.updated_at.isoformat()


class PhotoSerializerRobocassa(serializers.ModelSerializer):
    sum = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    tax = serializers.SerializerMethodField()

    class Meta:
        model = Photo
        fields = [
            "name",
            "sum",
            "quantity",
            "tax",
        ]

    def get_quantity(self, obj: Photo):
        return 1

    def get_tax(self, obj: Photo):
        return 'none'

    def get_sum(self, obj: Photo):
        try:
            if not obj.act.event.group.base_sale:
                order: Order = self.parent.parent.instance
                _, order_sale = get_order_sale(order)
                return math.floor(obj.act.event.group.price * (1 - order_sale / 100))
            return obj.act.event.group.base_sale
        except Exception:
            return None


class OrderSerializerRobocassa(serializers.ModelSerializer):
    order_list = PhotoSerializerRobocassa(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['order_id', 'order_list',]


class PhotoOrderSerializer(PhotoSerializer):
    preview_url = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()

    class Meta:
        model = Photo
        fields = ['preview_url', 'photo_orient', 'photo_id', 'photo_coast', 'photo_sale_coast', 'price', 'deleted_at']

    def get_preview_url(self, obj: Photo):
        return obj.preview_url_host

    def get_price(self, obj: Photo):
        order = self.context.get('current_order')
        try:
            return Purchase.objects.get(order=order, photo=obj).purchase_price
        except Exception:
            return None


class OrderPayedSerializer(OrderSerializer):
    order_list = serializers.SerializerMethodField()
    payed_date = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['order_id', 'order_coast', 'order_sale',
                  'order_sale_coast', 'order_list', 'payed_date']

    def get_order_list(self, obj: Order):
        return PhotoOrderSerializer(obj.order_list.all(), many=True, context={'current_order': obj}).data

    def get_payed_date(self, obj: Order):
        return obj.payed_date.isoformat()
