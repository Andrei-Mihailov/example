import textwrap

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from Users.models import CallbackUrls, Users

HOST_URL = settings.ALLOWED_HOSTS[0]


def email_confirm(call_user: CallbackUrls):
    header = f"Спасибо за регистрацию на нашем сайте {HOST_URL}!"
    text1 = "Для подтверждения вашего адреса электронной почты и активации вашей учетной записи, пожалуйста, перейдите по следующей ссылке:"
    link = f"https://{HOST_URL}/api/v1/users/confirm/{call_user.uuid}"
    text2 = "Это важный шаг для обеспечения безопасности вашей учетной записи и дальнейшего использования наших услуг."
    footer_text = "Если вы не регистрировались на нашем сайте, просто проигнорируйте это сообщение."
    footer_signature1 = "С уважением,"
    footer_signature2 = f"Команда {HOST_URL}"
    msg_html = render_to_string('email.html', {'header': header,
                                               'text1': text1,
                                               'button': "Активация аккаунта",
                                               'link': link,
                                               'text2': text2,
                                               'footer_text': footer_text,
                                               'footer_signature1': footer_signature1,
                                               'footer_signature2': footer_signature2})
    return msg_html


def email_change_password(call_user: CallbackUrls):
    header = f"Здравствуйте, {call_user.user.first_name}"
    text1 = "Мы получили Ваш запрос на сброс пароля для личного кабинета. Чтобы завершить процесс, пожалуйста, перейдите по ссылке ниже:"
    link = f"https://{HOST_URL}/reset_password/{call_user.uuid}"
    text2 = "После перехода Вы сможете установить новый пароль. Обратите внимание, что ссылка действительна в течение 24 часов."
    footer_text = "Если Вы не отправляли этот запрос, пожалуйста, незамедлительно сообщите нам об этом. Мы примем необходимые меры для защиты Ваших данных."
    footer_signature1 = "С уважением,"
    footer_signature2 = f"Команда {HOST_URL}"
    msg_html = render_to_string('email.html', {'header': header,
                                               'text1': text1,
                                               'button': "Сброс пароля",
                                               'link': link,
                                               'text2': text2,
                                               'footer_text': footer_text,
                                               'footer_signature1': footer_signature1,
                                               'footer_signature2': footer_signature2})
    return msg_html


def email_data_changed(user: Users):
    header = f"Здравствуйте, {user.first_name}"
    text1 = "Вы успешно изменили данные от Вашего личного кабинета. Теперь Вы можете использовать новые данные или пароль для авторизации."
    link = f"https://{HOST_URL}"
    text2 = "Пожалуйста, не передавайте свой пароль третьим лицам и не используйте его на других сайтах."
    footer_text = 'Письмо отправлено автоматически. Пожалуйста, не отвечайте на него.'
    footer_signature1 = "С уважением,"
    footer_signature2 = f"Команда {HOST_URL}"
    msg_html = render_to_string('email.html', {'header': header,
                                               'text1': text1,
                                               'button': "Перейти на сайт",
                                               'link': link,
                                               'text2': text2,
                                               'footer_text': footer_text,
                                               'footer_signature1': footer_signature1,
                                               'footer_signature2': footer_signature2})
    return msg_html


def email_feedback(user: Users):
    header = f"Здравствуйте, {user.first_name}"
    text1 = "Мы получили Ваше обращение через форму обратной связи на нашем сайте. Благодарим Вас за то, что Вы нашли время задать нам вопрос или сообщить о проблеме."
    text2 = "Пожалуйста, ожидайте ответа от нашей службы поддержки."
    footer_text = "Если у Вас возникнут дополнительные вопросы, мы будем рады на них ответить."
    footer_signature1 = "С уважением,"
    footer_signature2 = f"Команда {HOST_URL}"
    msg_html = render_to_string('email.html', {'header': header,
                                               'text1': text1,
                                               'text2': text2,
                                               'footer_text': footer_text,
                                               'footer_signature1': footer_signature1,
                                               'footer_signature2': footer_signature2})
    return msg_html


def email_paymend_fail(user: Users):
    header = f"Здравствуйте, {user.first_name}"
    text1 = "К сожалению, Ваш платеж не был обработан. Возможные причины могут быть связаны с проблемами на стороне банка или эквайринга."
    text2 = textwrap.dedent("""
        Пожалуйста, попробуйте провести операцию платежа позже или воспользуйтесь другим способом оплаты.
        Если проблема сохраняется, пожалуйста, свяжитесь со службой поддержки Вашего банка или технической поддержкой Robokassa по ссылке: https://robokassa.com/contacts.php
    """)

    footer_text = "Приносим извинения за неудобства и благодарим Вас за терпение."
    footer_signature1 = "С уважением,"
    footer_signature2 = f"Команда {HOST_URL}"
    msg_html = render_to_string('email.html', {'header': header,
                                               'text1': text1,
                                               'text2': text2,
                                               'footer_text': footer_text,
                                               'footer_signature1': footer_signature1,
                                               'footer_signature2': footer_signature2})
    return msg_html


def email_paymend_accept(user: Users):
    header = f"Здравствуйте, {user.first_name}"
    text1 = textwrap.dedent("""
        Мы хотим поблагодарить Вас за оплату заказа на нашем сайте. Ваш платеж был успешно обработан.
        Скачать купленные фотографии Вы можете в своём личном кабинете
    """)
    link = f"https://{HOST_URL}/user_order"
    text2 = textwrap.dedent("""
        Если у Вас возникнут какие-либо вопросы, пожалуйста, свяжитесь с нами через форму обратной связи на сайте или по почте:
    """)
    email = "support@mydance.photo"
    footer_text = 'Письмо отправлено автоматически. Пожалуйста, не отвечайте на него.'
    footer_signature1 = "С уважением,"
    footer_signature2 = f"Команда {HOST_URL}"
    msg_html = render_to_string('email.html', {'header': header,
                                               'text1': text1,
                                               'link': link,
                                               'text2': text2,
                                               'email': email,
                                               'footer_text': footer_text,
                                               'footer_signature1': footer_signature1,
                                               'footer_signature2': footer_signature2})
    return msg_html


def email_order_links(user: Users, order):
    header = f"Здравствуйте, {user.first_name}"
    text1 = textwrap.dedent(f"""
        Благодарим Вас за заказ №{order.order_id}.
        <br><br>
        По ссылкам ниже Вы можете скачать купленные фотографии.
        <br><br>
        """)
    text1 += '<br>'.join([f'https://{HOST_URL}/media/download_orders/' +
                          photo.name for photo in order.order_list.all()])
    text1 += textwrap.dedent("""
        <br><br>
        Ссылки действительны в течение 24 часов.
        <br><br>
        Так же в любое время Вы можете скачать купленные фотографии в личном кабинете, раздел «Мои заказы». Фото скачиваются на телефон или компьютер в папку «Загрузки»
    """)
    footer_text = 'Письмо отправлено автоматически. Пожалуйста, не отвечайте на него.'
    footer_signature1 = "С уважением,"
    footer_signature2 = f"Команда {HOST_URL}"
    msg_html = render_to_string('email.html', {'header': header,
                                               'text1': mark_safe(text1),
                                               'footer_text': footer_text,
                                               'footer_signature1': footer_signature1,
                                               'footer_signature2': footer_signature2})
    return msg_html


def email_photos_remove(user: Users, time):
    header = f"Здравствуйте, {user.first_name}"
    text1 = f"Рекомендуем Вам завершить покупку, или скачать уже купленные Вами фото на нашем сайте {HOST_URL}"
    link = f"https://{HOST_URL}/user_order"
    text2 = f"Так как фотографии в вашей корзине или личном кабинете будут удалены {time} и станут недоступны."
    footer_text = 'Письмо отправлено автоматически. Пожалуйста, не отвечайте на него.'
    footer_signature1 = "С уважением,"
    footer_signature2 = f"Команда {HOST_URL}"
    msg_html = render_to_string('email.html', {'header': header,
                                               'text1': text1,
                                               'button': "Перейти на сайт",
                                               'link': link,
                                               'text2': text2,
                                               'footer_text': footer_text,
                                               'footer_signature1': footer_signature1,
                                               'footer_signature2': footer_signature2})
    return msg_html


def email_sender(user: Users, message):
    header = f"Здравствуйте, {user.first_name}"
    text1 = message
    footer_text = 'Письмо отправлено автоматически. Пожалуйста, не отвечайте на него.'
    footer_signature1 = "С уважением,"
    footer_signature2 = f"Команда {HOST_URL}"
    msg_html = render_to_string('email.html', {'header': header,
                                               'text1': text1,
                                               'footer_text': footer_text,
                                               'footer_signature1': footer_signature1,
                                               'footer_signature2': footer_signature2})
    return msg_html


def email_reminder(user: Users):
    header = f"Здравствуйте, {user.first_name}"
    text1 = textwrap.dedent("""
        Мы бережно сохранили выбранные Вами фотографии.
        Перейдите по ссылке ниже, чтобы продолжить оформление заказа.
    """)
    link = f"https://{HOST_URL}/user_order"
    footer_text = 'Письмо отправлено автоматически. Пожалуйста, не отвечайте на него.'
    footer_signature1 = "С уважением,"
    footer_signature2 = f"Команда {HOST_URL}"
    msg_html = render_to_string('email.html', {'header': header,
                                               'text1': text1,
                                               'button': "Перейти на сайт",
                                               'link': link,
                                               'footer_text': footer_text,
                                               'footer_signature1': footer_signature1,
                                               'footer_signature2': footer_signature2})
    return msg_html
