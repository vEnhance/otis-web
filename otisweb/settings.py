"""
Django settings for otisweb project.
"""

import logging
import os
from pathlib import Path
from typing import Any

import django_discordo
import django_stubs_ext
import import_export.tmp_storages
from dotenv import load_dotenv

django_stubs_ext.monkeypatch()

BASE_DIR = Path(__file__).parent.parent.absolute()
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Manually added settings
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"
LOGIN_REDIRECT_URL = "/"

PRODUCTION = bool(int(os.getenv("IS_PRODUCTION") or 0))
DEBUG = not PRODUCTION
if PRODUCTION:
    ALLOWED_HOSTS = ["otis.evanchen.cc", ".localhost", "127.0.0.1"]
    CSRF_TRUSTED_ORIGINS = [
        "https://otis.evanchen.cc",
    ]
    SITE_URL = "https://otis.evanchen.cc/"
else:
    INTERNAL_IPS = [
        "127.0.0.1",
    ]
    SITE_URL = "http://127.0.0.1"
SITE_ID = 1
FORMS_URLFIELD_ASSUME_HTTPS = True
TESTING = False

# Application definition

INSTALLED_APPS = [
    "aincrad",
    "arch",
    "core",
    "dashboard",
    "exams",
    "hanabi",
    "markets",
    "mouse",
    "opal",
    "roster",
    "rpg",
    "payments",
    "suggestions",
    "tubes",
    # ------------
    "otisweb",
    # ------------
    "markdownfield",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.humanize",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.staticfiles",
]

if DEBUG is True and TESTING is False:
    INSTALLED_APPS.append("debug_toolbar")

INSTALLED_APPS += [
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.discord",
    "allauth.socialaccount.providers.github",
    "allauth.socialaccount.providers.google",
    "crispy_bootstrap5",
    "crispy_forms",
    "django_bootstrap5",
    "django_extensions",
    "django_nyt.apps.DjangoNytConfig",
    "hijack",
    "hijack.contrib.admin",
    "import_export",
    "markdownify.apps.MarkdownifyConfig",
    "mptt",
    "qr_code",
    "reversion",
    "sekizai",
    "sorl.thumbnail",
    "wiki.apps.WikiConfig",
    "wiki.plugins.editsection.apps.EditSectionConfig",
    "wiki.plugins.globalhistory.apps.GlobalHistoryConfig",
    "wiki.plugins.help.apps.HelpConfig",
    "wiki.plugins.images.apps.ImagesConfig",
    "wiki.plugins.links.apps.LinksConfig",
    "wiki.plugins.macros.apps.MacrosConfig",
    "wiki.plugins.redlinks.apps.RedlinksConfig",
    "wikihaxx",
]

if DEBUG is True and TESTING is False:
    MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"]
else:
    MIDDLEWARE = []

MIDDLEWARE += [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "hijack.middleware.HijackUserMiddleware",
    "core.middleware.LastSeenMiddleware",
]

ROOT_URLCONF = "otisweb.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "sekizai.context_processors.sekizai",
            ],
            "debug": not PRODUCTION,
        },
    },
]

WSGI_APPLICATION = "otisweb.wsgi.application"

# Database

if os.getenv("DATABASE_NAME"):
    DATABASES: dict[str, Any] = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DATABASE_NAME"),
            "USER": os.getenv("DATABASE_USER"),
            "PASSWORD": os.getenv("DATABASE_PASSWORD"),
            "HOST": os.getenv("DATABASE_HOST"),
            "PORT": os.getenv("DATABASE_PORT", "3306"),
            "OPTIONS": {
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
                "charset": "utf8mb4",
                "use_unicode": True,
            },
        },
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https" if PRODUCTION else "http"
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_PRESERVE_USERNAME_CASING = False
ACCOUNT_SIGNUP_FORM_CLASS = "otisweb.forms.OTISUserRegistrationForm"
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
SOCIALACCOUNT_EMAIL_REQUIRED = True

# Internationalization

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/New_York"
USE_I18N = True
USE_L10N = False
USE_TZ = True

DATETIME_FORMAT = "d M Y H:i:s"
DATE_FORMAT = "d M Y"
TIME_FORMAT = "H:i:s"
SHORT_DATE_FORMAT = "Y-m-d"  # ISO 8601

# Static files (CSS, JavaScript, Images)

STATIC_ROOT = BASE_DIR / "static/"
MEDIA_ROOT = BASE_DIR / "media/"

if PRODUCTION:
    STORAGES = {
        "default": {"BACKEND": "storages.backends.gcloud.GoogleCloudStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
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
    STATIC_URL = "/static/"
    MEDIA_URL = "/media/"
    SECRET_KEY = "evan_chen_is_really_cool"

TESTING_NEEDS_MOCK_MEDIA = False  # true only for a few tests

FILE_UPLOAD_HANDLERS = ("django.core.files.uploadhandler.MemoryFileUploadHandler",)
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

# Custom Evan keys
INVOICE_HASH_KEY = os.getenv("INVOICE_HASH_KEY", "evan_chen_is_still_really_cool")
STORAGE_HASH_KEY = os.getenv("STORAGE_HASH_KEY", "look_at_me_im_a_cute_kitten")
CERT_HASH_KEY = os.getenv("CERT_HASH_KEY", "certified_by_god")
OPAL_HASH_KEY = os.getenv("OPAL_HASH_KEY", "paradise_is_where_i_am")
API_TARGET_HASH = os.getenv("API_TARGET_HASH")

PATH_STATEMENT_ON_DISK = os.getenv("PATH_STATEMENT_ON_DISK")

# Discord webhook configuration for logging
DISCORD_WEBHOOK_URLS = {
    "CRITICAL": os.getenv("DISCORD_WEBHOOK_URL_CRITICAL"),
    "ERROR": os.getenv("DISCORD_WEBHOOK_URL_ERROR"),
    "WARNING": os.getenv("DISCORD_WEBHOOK_URL_WARNING"),
    "SUCCESS": os.getenv("DISCORD_WEBHOOK_URL_SUCCESS"),
    "ACTION": os.getenv("DISCORD_WEBHOOK_URL_ACTION"),
    "DEFAULT": os.getenv("DISCORD_WEBHOOK_URL"),
}

STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_ENDPOINT_SECRET = os.getenv("STRIPE_ENDPOINT_SECRET")

WIKI_ACCOUNT_HANDLING = False
WIKI_ACCOUNT_SIGNUP_ALLOWED = False
WIKI_PLUGINS_METHODS = ("article_list", "toc", "meow")

MARKDOWNIFY = {
    "default": {
        "WHITELIST_TAGS": [
            "a",
            "b",
            "blockquote",
            "em",
            "hr",
            "i",
            "li",
            "ol",
            "p",
            "strong",
            "ul",
        ]
    }
}


# Filters out the OSError: WriteError messages that keep popping up in WSGI
def filter_oserror_write(record: logging.LogRecord) -> bool:
    return not (
        hasattr(record, "message") and record.message.startswith("OSError: write error")
    )


def add_username(record: logging.LogRecord):
    try:
        record.username = record.request.user.username  # type: ignore
    except AttributeError:
        record.username = ""
    return True


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "stream_format": {
            "format": "[{levelname}] {asctime} {module} {name} [{username}@{filename}:{lineno}]\n{message}\n",
            "style": "{",
        },
    },
    "filters": {
        "filter_oserror_write": {
            "()": "django.utils.log.CallbackFilter",
            "callback": filter_oserror_write,
        },
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
        "add_username": {
            "()": "django.utils.log.CallbackFilter",
            "callback": add_username,
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "VERBOSE",
            "formatter": "stream_format",
            "filters": ["filter_oserror_write", "add_username"],
        },
        "discord": {
            "class": "django_discordo.DiscordWebhookHandler",
            "level": "VERBOSE",
            "filters": ["require_debug_false", "filter_oserror_write", "add_username"],
        },
    },
    "root": {
        "handlers": ["console", "discord"],
        "level": "VERBOSE",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "discord"],
            "level": "VERBOSE",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "DEBUG",
            "filters": ["require_debug_true"],
        },
        "django.server": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "stripe": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
if TESTING:
    logging.disable(django_discordo.ACTION_LOG_LEVEL)
