# -*- coding: utf-8 -*-"""

"""
Django settings for wip project.

Generated by 'django-admin startproject' using Django 1.9.

For more information on this file, see
https://docs.djangoproject.com/en/1.9/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.9/ref/settings/
"""
from .private import *

import string
import os

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wip.settings')

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(PROJECT_DIR)

SILENCED_SYSTEM_CHECKS = []

# Application definition
INSTALLED_APPS = [
    'haystack',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    'django_extensions',
    'tinymce',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    #'allauth.socialaccount.providers.oauth2',
    # 'keyrock',
    'bootstrap3',
    'menu',
    'httpproxy',
    'actstream',
    'django_dag',
    'adminsortable2',
    'django_diazo',
    'rest_framework',
    'wip',
]

# MIDDLEWARE_CLASSES = [
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'wip.middleware.ProxyMiddleware',
    'django.middleware.http.ConditionalGetMiddleware',
]
if (sys.version_info < (3, 0)):
    MIDDLEWARE_CLASSES = MIDDLEWARE

ROOT_URLCONF = 'wip.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, "wip", "templates")],
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django_diazo.context_processors.diazo_enabled',
                'wip.context_processors.context_processor',
            ],
        'loaders': [
            'django.template.loaders.filesystem.Loader',
            'django.template.loaders.app_directories.Loader',
            ],
        },
    },
]
if DEBUG:
    TEMPLATES[0]['OPTIONS']['string_if_invalid'] = '%s'

WSGI_APPLICATION = 'wip.wsgi.application'

# Password validation
# https://docs.djangoproject.com/en/1.9/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/1.9/topics/i18n/

LANGUAGE_CODE = 'en-us'

# TIME_ZONE = 'UTC'
TIME_ZONE = 'Europe/Rome'
USE_TZ = True
SHORT_DATETIME_FORMAT = 'd-m-y P'
DATETIME_FORMAT = 'd-m-y H'

USE_I18N = True
USE_L10N = True

SITE_ID = 1
SITE_NAME = 'FairVillage - WIP'

LOGIN_REDIRECT_URL = '/'

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.9/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
CACHE_ROOT = os.path.join(BASE_DIR, 'cache')

BROKER_URL = 'amqp://guest:guest@localhost:5672//'

# Cache backend is optional, but recommended to speed up user agent parsing
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    },
    'resources': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': os.path.join(BASE_DIR, 'cache/resources'),
        'TIMEOUT': 24*60*60,
        'MAX_ENTRIES': 1000,
    },
}

"""
logging levels:
DEBUG: Low level system information for debugging purposes
INFO: General system information
WARNING: Information describing a minor problem that has occurred.
ERROR: Information describing a major problem that has occurred.
CRITICAL: Information describing a critical problem that has occurred.
"""
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'file': {
            'level': 'DEBUG',
            'filters': ['require_debug_false'],
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'debug.log'),
        },
        'wip': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'wip.log'),
        },
        'django': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'django.log'),
        },
    },
    'loggers': {
        'shell': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
        'django': {
            'handlers': ['console', 'django'],
            'level': 'INFO',
            'propagate': True,
        },
        'wip': {
            'handlers': ['wip'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# NLTK and other linguistic resources

NLTK_DATA_PATH = ''
LEXICONS = ''
CORPORA = ''
DATA_ROOT = os.path.join(BASE_DIR, 'data')
SITES_ROOT = os.path.join(BASE_DIR, 'sites')
RESOURCES_ROOT = os.path.join(PROJECT_DIR, 'resources')

# morphit_path = "/Tecnica/CL/risorse/italiano/morph-it/morph-it.48/morph-it_048.txt"
morphit_filename = "morph-it_048.txt"
morphit_path = os.path.join(RESOURCES_ROOT, morphit_filename)
# tagger_filename = "itwac-1.2000000.biunigram.affix-2.simplified.pickle"
tagger_filename = "ITWAC-1.xml.pickle"
BLOCK_TAGS = [
   'html', 'body', 'header', 'hgroup', 'main',  'aside', 'footer',
   'address', 'article', 'field', 'section', 'nav',
   'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'dl', 'dt', 'dd',
   'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td',
   'blockquote', 'pre', 'noscript', 'br',
   'img', 'figure', 'figcaption', 'canvas', 'video',
   'form', 'fieldset', 'input', 'button', 'select', 'option', 'textarea', 'output',
]
TO_DROP_TAGS = [
    'head', 'link', 'script', 'style','iframe',
]

QUOTES = (
 ('"', '"',),
 ('“', '”',),
 ('‘', '’',),
)

BOTH_QUOTES = '\'"'
# TRANS_QUOTES = string.maketrans("‘’“”", "''\"\"")
TRANS_QUOTES = {
    ord(u"\u2018"): u"'",
    ord(u"\u2019"): u"'",
    ord(u"\u201C"): u'"',
    ord(u"\u201D"): u'"',
}
tab_in = "‘’“”"
tab_out = "''\"\""
TRANS_QUOTES = dict(zip(tab_in, tab_out))

EMPTY_WORDS = {
'en': [
       'a', 'an', 'the', 
       'after', 'among', 'at', 'before', 'for', 'in', 'of', 'on', 'over', 'to', 'with',
       'and', 'or', 'not',
],
'es': [],
'fr': [],
'it': [
       'e', 'o', 'ma',
       'di', 'a', 'da', 'in', 'con', 'su', 'per',
       'del', 'della', 'dei', 'al', 'alla', 'ai', 'sui',
       'fra', 'tra', 'uno', 'una', 'tutti', 'tutte',
       'tuo', 'tua', 'tuoi', 'tue',
       'quello', 'quella', 'questo', 'questa',
       'chi', 'che',
       'poco', 'molto', 'tanto',
       'circa', 'solo', 'anche', 'pure', 'però',
],
}

SEPARATORS =  {
'en': u' .,;:?*/+-–()[]{}',
'es': u' .,;:?*/+-–()[]{}',
'fr': u' .,;:?*/+-–()[]{}',
'it': u' .,;:?*/+-–()[]{}',
}
STRIPPED =  {
'en': u' .,;:?*/+-–()[]{}\"\“\”\xa0',
'es': u' .,;:?*/+-–()[]{}\"\“\”\xa0',
'fr': u' .,;:?*/+-–()[]{}\"\“\”\xa0',
'it': u' .,;:?*/+-–()[]{}\"\“\”\xa0',
}

DEFAULT_STRIPPED = STRIPPED['en']
LANGUAGE_COLORS = { 'it': 'green', 'en': 'grey', 'es': 'red', 'fr': 'blue', }

PAGES_EXCLUDE_BY_CONTENT = {
  'scuolemigranti': [
     '/category/archivio/notizie/',
  ]
}

BLOCKS_EXCLUDE_BY_XPATH = {
  'scuolemigranti': [
     '/html/body/div/div/div[1]/div[3]/div[2]',
  ]
}


# configure graph_models command of django-extensions
GRAPH_MODELS = {
  'all_applications': False,
  'group_models': False,
}

# TinyMCE settings (from roma APP of RomaPaese project)
TINYMCE_COMPRESSOR = True

TINYMCE_DEFAULT_CONFIG = {
    'width': '640', # '400',
    'height': '480', # '300',
    'plugins': 'fullscreen,media,preview,paste,table',
    'theme': 'advanced',
    'relative_urls': False,
    'theme_advanced_toolbar_location': 'top',
    'theme_advanced_toolbar_align': 'left',
    'theme_advanced_buttons1': 'undo,redo,|,formatselect,bold,italic,underline,|,' \
        'justifyleft,justifycenter,justifyright,justifyfull,|,forecolor,backcolor,' \
        'sub,sup,charmap,|,bullist,numlist,|,indent,outdent,|,link,unlink,anchor,image,media',
    'theme_advanced_buttons2': '|,tablecontrols,|,cut,copy,paste,pasteword,pastetext,selectall,|,removeformat,cleanup,|,visualaid,code,preview,fullscreen',
    'theme_advanced_buttons3': '',
    'theme_advanced_blockformats': 'p,pre,address,blockquote,h1,h2,h3,h4,' \
        'h5,h6',
    'plugin_preview_width' : '800',
    'plugin_preview_height' : '600',
    'paste_auto_cleanup_on_paste': 'false',
    }

HAYSTACK_LIMIT_TO_REGISTERED_MODELS = False
SEARCH_BACKEND = "whoosh"
if SEARCH_BACKEND == 'whoosh':
    HAYSTACK_CONNECTIONS = {
        'default': {
            'ENGINE': 'haystack.backends.whoosh_backend.WhooshEngine',
            'PATH': os.path.join(BASE_DIR, 'whoosh_index'),
        },
    }

REST_FRAMEWORK = {
    # Use Django's standard `django.contrib.auth` permissions,
    # or allow read-only access for unauthenticated users.
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly'
    ],
}

PAGE_SIZE = 100
PAGE_STEPS = [1, 2, 3, 4, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]

