import os

EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = os.getenv('EMAIL_PORT')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_POP3 = os.getenv('EMAIL_HOST_POP3')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
SERVER_EMAIL = EMAIL_HOST_USER
EMAIL_BACKEND = 'django_smtp_ssl.SSLEmailBackend'
EMAIL_USE_SSL = True
DEFAULT_FROM_EMAIL = f"Техподдержка сайта mydance.photo <{EMAIL_HOST_USER}>"
EMAIL_FILE_PATH = os.getenv('EMAIL_FILE_PATH')
MAILBOXES = {
    'inbox': {
        'ENGINE': 'django_mailbox.pop3',
        'OPTIONS': {
            'host': EMAIL_HOST_POP3,
            'username': EMAIL_HOST_USER,
            'password': EMAIL_HOST_PASSWORD,
            'ssl': True,
        }
    }
}
