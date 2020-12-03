"""
Django settings for webapp project.

Generated by 'django-admin startproject' using Django 2.1.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""
from datetime import datetime
import os
import dj_database_url
import pytz

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WEBAPP_VERSION = "0.1.0"

ADMINS = [("Hank", "hank@compute.studio")]

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "test-key-only")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False if os.environ.get("DEBUG", "False") == "False" else True

ALLOWED_HOSTS = ["*"]
# enforce HTTPS/SSL
SECURE_SSL_REDIRECT = False if os.environ.get("LOCAL", "") else True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CSRF_COOKIE_NAME = "csrftoken"

USE_STRIPE = os.environ.get("USE_STRIPE", "false").lower() == "true"

DEFAULT_CLUSTER_USER = os.environ.get("DEFAULT_CLUSTER_USER")
DEFAULT_VIZ_HOST = os.environ.get("DEFAULT_VIZ_HOST")

# Number of private sims available/month on free tier.
FREE_PRIVATE_SIMS = 3
FREE_PRIVATE_SIMS_START_DATE = pytz.timezone("US/Eastern").localize(
    datetime(2019, 11, 17, 0, 0, 0),
)

# Indicates that this c/s instance uses billing restrictions.
HAS_USAGE_RESTRICTIONS = (
    os.environ.get("HAS_USAGE_RESTRICTIONS", "true").lower() == "true"
)

COMPUTE_PRICING = {"cpu": 0.021811, "memory": 0.002923}


def get_salt(env_var, dev_value):
    salt = os.environ.get(env_var, None)
    if salt:
        return salt
    else:
        return dev_value


INPUTS_SALT = get_salt("INPUTS_SALT", "dev-inputs-salt")


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "rest_framework",
    "rest_framework.authtoken",
    "webapp.apps.comp",
    "webapp.apps.pages",
    "webapp.apps.users",
    "webapp.apps.billing",
    "webapp.apps.publish",
    # third-party apps
    "widget_tweaks",
    "crispy_forms",
    "guardian",
    "rest_auth",
    "allauth",
    "allauth.account",
    "rest_auth.registration",
    "allauth.socialaccount",
    "anymail",
    # 'allauth.socialaccount.providers.github', # new
]

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}

MIDDLEWARE = [
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "webapp.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR + "/templates/"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "webapp.apps.pages.context_processors.project_list",
            ]
        },
    }
]

CRISPY_TEMPLATE_PACK = "bootstrap4"

WSGI_APPLICATION = "webapp.wsgi.application"


# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases


def default_db_url():
    db_config = dj_database_url.config()
    if os.environ.get("POSTGRES_PASSWORD"):
        return dict(
            db_config, USER="postgres", PASSWORD=os.environ.get("POSTGRES_PASSWORD")
        )
    else:
        return db_config


DATABASES = {
    "default": default_db_url(),
    # override database name for tests.
    "TEST": dict(default_db_url(), **{"NAME": "testdb",}),
}

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",  # default
    "guardian.backends.ObjectPermissionBackend",
)

SITE_ID = 1

# Login routing
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
LOGIN_URL = "/users/login/"

# For custom user class
AUTH_USER_MODEL = "users.User"

# diable django-allauth email verification for now.
# https://django-allauth.readthedocs.io/en/latest/configuration.html
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_AUTHENTICATION_METHOD = "username_email"
ACCOUNT_UNIQUE_EMAIL = False

# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

ACCOUNT_AUTHENTICATION_METHOD = "username"


# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Email backend for developing pw reset functionality
EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = os.path.join(BASE_DIR, "sent_emails")

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]


ANYMAIL = {
    # (exact settings here depend on your ESP...)
    "MAILGUN_API_KEY": os.environ.get("MAILGUN_API_KEY"),
    "MAILGUN_SENDER_DOMAIN": "mg.compute.studio",  # your Mailgun domain, if needed
}
EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"
DEFAULT_FROM_EMAIL = "hank@compute.studio"
SERVER_EMAIL = "hank@compute.studio"


if not os.environ.get("LOCAL") and os.environ.get("SENTRY_API_DSN"):
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=os.environ.get("SENTRY_API_DSN"),
        integrations=[DjangoIntegration()],
        send_default_pii=True,
        traces_sample_rate=0.75,
    )
