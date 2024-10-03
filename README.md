## Пример моего кода из последнего проекта

Представлены модули catalog, emails и api, а также настройки проекта Mydance

# В модуле catalog продемонстрированы:

- часть задач celery, работающие непосредственно с облачным хранилищем Яндекс.Диск, с обработкой фотографий, их загрузкой, а также с отложенным взаимодействием с фотографиями, концертам и т.д.;
- админка Django для управления сайтом и каталогом фотографий;
- взаимодействие с обработчиками сигналов Django.

# В модуле emails продемонстрированы:

- часть задач celery, работающие c рассылкой email уведомлений пользователям через админку Django, проверкой почтового ящика;
- админка Django для работы с почтой прямо на сайте.

## Используемый стек:

### Веб-фреймворки и API:

- Django
- DRF (Django Rest Framework)
- adrf (Async Django REST framework)
- channels

### Асинхронное программирование:

- aiohttp
- asyncio
- httpx

### Задачи и планировщики:

- Celery

### Работа с окружением и конфигурацией:

- dotenv
- split_settings

### Работа с данными и файлами:

- json
- requests
- zipfile
- PIL (Pillow)
- image_to_numpy
- numpy
- pillow_heif

### Утилиты и стандартные библиотеки:

- pathlib
- io
- jwt
- textwrap
- linecache
- hashlib
- urllib
- functools
- uuid
- secrets
- datetime
- imaplib
- email
- quopri
- base64

### Специфические библиотеки:

- yadisk
- face_recognition
- imbox
