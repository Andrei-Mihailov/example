from pathlib import Path
import os
from dotenv import load_dotenv
from split_settings.tools import include


load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent
ADD_PATH = os.path.join(BASE_DIR)

SECRET_KEY = os.environ.get('SECRET_KEY')

DEBUG = os.environ.get('DEBUG', False) == 'True'
if DEBUG:
    PREPEND_PATH = ''
else:
    PREPEND_PATH = '/home/admin/web/mydance.photo/public_html/'


include(
    'components/database.py',
    'components/installed_apps.py',
    'components/middlewares.py',
    'components/templates.py',
    'components/pass_validators.py',
    'components/email_data.py',
    'components/yandex_id.py',
    'components/vk_id.py',
    'components/disk.py',
    'components/celery.py',
    'components/caches.py',
    'components/robokassa.py'

)

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS').replace(
    '[', '').replace(']', '').replace('\'', '').split(',')

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)
CSRF_TRUSTED_ORIGINS = [
    'https://photo.valyaev.pro/',
    'https://auth.robokassa.ru',
    'https://robotike.com',
    'https://mydance.photo'
]

APPEND_SLASH = True
USER_ONLINE_TIMEOUT = 300
USER_LASTSEEN_TIMEOUT = 60 * 60 * 24 * 7

X_FRAME_OPTIONS = 'ALLOWALL'

ROOT_URLCONF = 'Mydance.urls'

WSGI_APPLICATION = 'Mydance.wsgi.application'

LANGUAGE_CODE = 'ru-ru'

TIME_ZONE = 'Europe/Moscow'

USE_I18N = True

USE_L10N = True

USE_TZ = True

STATIC_URL = '/static/'

MEDIA_URL = '/media/'

STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]

MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
CRISPY_TEMPLATE_PACK = 'bootstrap4'
LOGIN_REDIRECT_URL = '/'
LOGIN_URL = '/'
SESSION_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SECURE = True

CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
]
CORS_ALLOWED_ORIGIN_REGEXES = [
    'http://localhost:5173',
]
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
