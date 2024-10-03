import decimal
import hashlib
import json
import requests

from urllib import parse
from urllib.parse import urlparse
from Mydance.settings import ROBOKASSA_LOGIN, ROBOKASSA_PASSWORD_1, ROBOKASSA_PASSWORD_2, ROBOKASSA_TEST
from Basket.models import Order
from .serializer import OrderSerializerRobocassa


def calculate_signature(*args) -> str:
    """Create signature MD5.
    """
    return hashlib.sha256(':'.join(str(arg) for arg in args).encode()).hexdigest()


def parse_response(request: str) -> dict:
    """
    :param request: Link.
    :return: Dictionary.
    """
    params = {}

    for item in urlparse(request).query.split('&'):
        key, value = item.split('=')
        params[key] = value
    return params


def check_signature_result(
    order_number: int,  # invoice number
    received_sum: decimal,  # cost of goods, RU
    received_signature: hex,  # SignatureValue
    password: str  # Merchant password
) -> bool:
    signature = calculate_signature(received_sum, order_number, password)
    if signature.lower() == received_signature.lower():
        return True
    return False


class CustomQuote:
    def __init__(self, safe=''):
        self.safe = safe

    def __quote(self, s):
        return s.replace('=', '%3A').replace('&', '%2C').replace(' ', '%22')

    def __call__(self, value, safe='/'):
        return self.__quote(value)
# Формирование URL переадресации пользователя на оплату.


def generate_payment_link(
    cost: decimal,  # Cost of goods, RU
    number: int,  # Invoice number
    order: Order
) -> str:
    """URL for redirection of the customer to the service.
    """
    data_items = OrderSerializerRobocassa(order).data['order_list']
    Receipt = {
        "items": [dict(item) for item in data_items],
    }
    encoded_receipt_str = ''.join(parse.quote(char) for char in json.dumps(Receipt)).replace("%20", "")
    signature = calculate_signature(
        ROBOKASSA_LOGIN,
        cost,
        number,
        encoded_receipt_str,
        ROBOKASSA_PASSWORD_1
    )

    data = {
        'MerchantLogin': ROBOKASSA_LOGIN,
        'OutSum': cost,
        'InvId': number,
        'Description': "Цифровые фотографии",
        'Receipt': encoded_receipt_str,
        'SignatureValue': signature,
        'Culture': 'ru',
        'IsTest': ROBOKASSA_TEST
    }
    res = requests.post('https://auth.robokassa.ru/Merchant/Indexjson.aspx', data=data)
    invoiceID = json.loads(res.text)['invoiceID']
    return 'https://auth.robokassa.ru/Merchant/Index/' + invoiceID


# Получение уведомления об исполнении операции (ResultURL).

def result_payment(request: str) -> str:
    """Verification of notification (ResultURL).
    :param request: HTTP parameters.
    """
    param_request = parse_response(request)
    cost = param_request['OutSum']
    number = param_request['InvId']
    signature = param_request['SignatureValue']

    if check_signature_result(number, cost, signature, ROBOKASSA_PASSWORD_2):
        return f'OK{param_request["InvId"]}'
    return "bad sign"


# Проверка параметров в скрипте завершения операции (SuccessURL).

def check_success_payment(request: str) -> str:
    """ Verification of operation parameters ("cashier check") in SuccessURL script.
    :param request: HTTP parameters
    """
    param_request = request.POST
    cost = param_request['OutSum']
    number = param_request['InvId']
    signature = param_request['SignatureValue']

    return check_signature_result(number, cost, signature, ROBOKASSA_PASSWORD_2)
