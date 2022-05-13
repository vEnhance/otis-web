"""
Django settings for otisweb project.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import django_stubs_ext
import dwhandler
import import_export.tmp_storages
from dotenv import load_dotenv

django_stubs_ext.monkeypatch()

assert dwhandler is not None

BASE_DIR = Path(__file__).parent.parent.absolute()
ENV_PATH = BASE_DIR / '.env'
if ENV_PATH.exists():
	load_dotenv(ENV_PATH)

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Manually added settings

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'
LOGIN_REDIRECT_URL = '/'

PRODUCTION = bool(int(os.getenv('IS_PRODUCTION') or 0))
DEBUG = not PRODUCTION
if PRODUCTION:
	ALLOWED_HOSTS = ['otis.evanchen.cc', '.localhost', '127.0.0.1']
	CSRF_TRUSTED_ORIGINS = [
		'https://otis.evanchen.cc',
	]
else:
	INTERNAL_IPS = [
		'127.0.0.1',
	]
SITE_ID = 1
TESTING = len(sys.argv) > 1 and sys.argv[1] == 'test'

# Application definition

INSTALLED_APPS = [
	'aincrad',
	'arch',
	'core',
	'dashboard',
	'exams',
	'markets',
	'mouse',
	'roster',
	'payments',
	'otisweb',
	'django.contrib.admin',
	'django.contrib.auth',
	'django.contrib.contenttypes',
	'django.contrib.humanize',
	'django.contrib.messages',
	'django.contrib.sessions',
	'django.contrib.sites',
	'django.contrib.staticfiles',
	'debug_toolbar',
	'allauth',
	'allauth.account',
	'allauth.socialaccount',
	'allauth.socialaccount.providers.discord',
	'allauth.socialaccount.providers.github',
	'allauth.socialaccount.providers.google',
	'bootstrap5',
	'crispy_forms',
	'crispy_bootstrap5',
	'hijack',
	'hijack.contrib.admin',
	'import_export',
	'reversion',
	'django_nyt.apps.DjangoNytConfig',
	'mptt',
	'sekizai',
	'sorl.thumbnail',
	'qr_code',
	'wiki.apps.WikiConfig',
	'wiki.plugins.editsection.apps.EditSectionConfig',
	'wiki.plugins.images.apps.ImagesConfig',
	'wiki.plugins.links.apps.LinksConfig',
	'wiki.plugins.macros.apps.MacrosConfig',
	'wiki.plugins.help.apps.HelpConfig',
	'wiki.plugins.globalhistory.apps.GlobalHistoryConfig',
	'wiki.plugins.redlinks.apps.RedlinksConfig',
	'wikihaxx',
]

MIDDLEWARE = [
	'debug_toolbar.middleware.DebugToolbarMiddleware',
	'django.middleware.security.SecurityMiddleware',
	'django.contrib.sessions.middleware.SessionMiddleware',
	'django.middleware.common.CommonMiddleware',
	'django.middleware.csrf.CsrfViewMiddleware',
	'django.contrib.auth.middleware.AuthenticationMiddleware',
	'django.contrib.messages.middleware.MessageMiddleware',
	'django.middleware.clickjacking.XFrameOptionsMiddleware',
	'hijack.middleware.HijackUserMiddleware',
	'core.middleware.LastSeenMiddleware',
]

ROOT_URLCONF = 'otisweb.urls'

TEMPLATES = [
	{
		'BACKEND': 'django.template.backends.django.DjangoTemplates',
		'DIRS': [],
		'APP_DIRS': True,
		'OPTIONS':
			{
				'context_processors':
					[
						'django.template.context_processors.debug',
						'django.template.context_processors.request',
						'django.contrib.auth.context_processors.auth',
						'django.contrib.messages.context_processors.messages',
						"sekizai.context_processors.sekizai",
					],
				'debug': not PRODUCTION,
			},
	},
]

WSGI_APPLICATION = 'otisweb.wsgi.application'

# Database
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases

if os.getenv("DATABASE_NAME"):
	DATABASES: Dict[str, Any] = {
		'default':
			{
				'ENGINE': 'django.db.backends.mysql',
				'NAME': os.getenv("DATABASE_NAME"),
				'USER': os.getenv("DATABASE_USER"),
				'PASSWORD': os.getenv("DATABASE_PASSWORD"),
				'HOST': os.getenv("DATABASE_HOST"),
				'PORT': os.getenv("DATABASE_PORT", '3306'),
				'OPTIONS':
					{
						'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
						'charset': 'utf8mb4',
						'use_unicode': True,
					},
			},
	}
else:
	DATABASES = {
		'default': {
			'ENGINE': 'django.db.backends.sqlite3',
			'NAME': BASE_DIR / 'db.sqlite3',
		}
	}

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
AUTHENTICATION_BACKENDS = [
	'django.contrib.auth.backends.ModelBackend',
	'allauth.account.auth_backends.AuthenticationBackend',
]

ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https" if PRODUCTION else "http"
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_PRESERVE_USERNAME_CASING = False
ACCOUNT_SIGNUP_FORM_CLASS = 'otisweb.forms.OTISUserRegistrationForm'
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
SOCIALACCOUNT_EMAIL_REQUIRED = True

# Internationalization
# https://docs.djangoproject.com/en/1.9/topics/i18n/

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/New_York'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.9/howto/static-files/

STATIC_ROOT = BASE_DIR / 'static/'
MEDIA_ROOT = BASE_DIR / 'media/'

if PRODUCTION:
	DEFAULT_FILE_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'
	STATIC_URL = os.getenv("STATIC_URL")
	GS_BUCKET_NAME = os.getenv("GS_BUCKET_NAME")
	MEDIA_URL = os.getenv("MEDIA_URL")
	assert STATIC_URL is not None
	assert GS_BUCKET_NAME is not None
	assert MEDIA_URL is not None
	IMPORT_EXPORT_TMP_STORAGE_CLASS = import_export.tmp_storages.CacheStorage
	SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
	assert SECRET_KEY is not None
else:
	STATIC_URL = '/static/'
	MEDIA_URL = '/media/'
	SECRET_KEY = 'evan_chen_is_really_cool'

FILE_UPLOAD_HANDLERS = ('django.core.files.uploadhandler.MemoryFileUploadHandler', )
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

# Custom Evan keys
INVOICE_HASH_KEY = os.getenv("INVOICE_HASH_KEY", "evan_chen_is_still_really_cool")
STORAGE_HASH_KEY = os.getenv("STORAGE_HASH_KEY", "look_at_me_im_a_cute_kitten")
CERT_HASH_KEY = os.getenv("CERT_HASH_KEY", "certified_by_god")
API_TARGET_HASH = os.getenv(
	"API_TARGET_HASH", '1c3592aa9241522fea1dd572c43c192a277e832dcd1ae63adfe069cb05624ead'
)
PATH_STATEMENT_ON_DISK = os.getenv("PATH_STATEMENT_ON_DISK", None)

STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_ENDPOINT_SECRET = os.getenv("STRIPE_ENDPOINT_SECRET")

WIKI_ACCOUNT_HANDLING = False
WIKI_ACCOUNT_SIGNUP_ALLOWED = False
WIKI_PLUGINS_METHODS = ('article_list', 'toc', 'meow')


def filter_useless_404(record: logging.LogRecord) -> bool:
	if record.args is None:
		return True
	a: List[str] = [str(s) for s in record.args]
	if len(a) == 2:
		return not (a[0] == 'Not Found' and ('wp-include' in a[1] or '.php' in a[1]))
	elif len(a) == 3:
		return not (a[1] == '404' and ('wp-include' in a[0] or '.php' in a[0]))
	else:
		return True


LOGGING = {
	'version': 1,
	'disable_existing_loggers': False,
	'formatters':
		{
			'stream_format':
				{
					'format': '[{levelname}] {asctime} {module} {name}\n{message}\n',
					'style': '{',
				},
		},
	'filters':
		{
			'filter_useless_404':
				{
					'()': 'django.utils.log.CallbackFilter',
					'callback': filter_useless_404,
				},
			'require_debug_false': {
				'()': 'django.utils.log.RequireDebugFalse',
			},
			'require_debug_true': {
				'()': 'django.utils.log.RequireDebugTrue',
			}
		},
	'handlers':
		{
			'console':
				{
					'class': 'logging.StreamHandler',
					'level': 'VERBOSE',
					'formatter': 'stream_format',
					'filters': ['filter_useless_404'],
				},
			'discord':
				{
					'class': 'dwhandler.DiscordWebhookHandler',
					'level': 'VERBOSE',
					'filters': ['require_debug_false', 'filter_useless_404'],
				}
		},
	'root': {
		'handlers': ['console', 'discord'],
		'level': 'INFO',
	},
	'loggers':
		{
			'django': {
				'handlers': ['console', 'discord'],
				'level': 'INFO',
				'propagate': False,
			},
			'django.db.backends':
				{
					'handlers': ['console'],
					'level': 'DEBUG',
					'filters': ['require_debug_true'],
				},
			'django.server': {
				'handlers': ['console'],
				'level': 'DEBUG',
				'propagate': False,
			},
			'mailchimp3.client': {
				'handlers': ['console'],
				'level': 'DEBUG',
				'propagate': False,
			},
		},
}
if TESTING:
	logging.disable(dwhandler.ACTION_LOG_LEVEL)
