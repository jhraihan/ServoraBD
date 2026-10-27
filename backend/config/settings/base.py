
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
    OTP_TTL_SECONDS=(int, 300),
    OTP_MAX_SENDS_PER_HOUR=(int, 3),
    OTP_MAX_VERIFY_ATTEMPTS=(int, 5),
    JWT_ACCESS_MINUTES=(int, 15),
    JWT_REFRESH_DAYS=(int, 14),
    PLATFORM_COMMISSION_PERCENT=(int, 12),
    TRUST_ALGO_VERSION=(str, "v1.0"),
    TRUSTED_PROXY_COUNT=(int, 0),
    USE_OBJECT_STORAGE=(bool, False),
    EXPOSE_CLIENT_IDENT=(bool, False),
)

environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")


DJANGO_APPS = [
    "unfold.apps.BasicAppConfig",
    "apps.common.admin_apps.ServoraAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "django_otp",
    "django_otp.plugins.otp_totp",
]

LOCAL_APPS = [
    "apps.common",
    "apps.operations",
    "apps.accounts",
    "apps.catalogue",
    "apps.providers",
    "apps.trust",
    "apps.bookings",
    "apps.reviews",
    "apps.payments",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS


MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "apps.common.middleware.ClientIdentHeaderMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = False
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "apps.accounts.backends.PhoneOrEmailBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation."
             "UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation."
             "CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation."
             "NumericPasswordValidator"},
]


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.ServoraJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "NUM_PROXIES": env("TRUSTED_PROXY_COUNT"),
    "DEFAULT_THROTTLE_RATES": {
        "search": "100/min",
        "register": "10/hour",
        "otp_send": "10/hour",
        "otp_verify": "30/hour",
        "service_request": "10/hour",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env("JWT_ACCESS_MINUTES")),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env("JWT_REFRESH_DAYS")),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_REFRESH_SERIALIZER":
        "apps.accounts.serializers.ServoraTokenRefreshSerializer",
}


LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "private": {
        "BACKEND": "apps.common.storage.PrivateMediaStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


OTP_TTL_SECONDS = env("OTP_TTL_SECONDS")
OTP_MAX_SENDS_PER_HOUR = env("OTP_MAX_SENDS_PER_HOUR")
OTP_MAX_VERIFY_ATTEMPTS = env("OTP_MAX_VERIFY_ATTEMPTS")
PLATFORM_COMMISSION_PERCENT = env("PLATFORM_COMMISSION_PERCENT")
TRUST_ALGO_VERSION = env("TRUST_ALGO_VERSION")

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")

SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

OTP_TOTP_ISSUER = "ServoraBD"

UNFOLD = {
    "SITE_TITLE": "ServoraBD admin",
    "SITE_HEADER": "ServoraBD",
    "SITE_SUBHEADER": "Operations",
    "SITE_SYMBOL": "handyman",
    "SHOW_VIEW_ON_SITE": False,
    "DASHBOARD_CALLBACK": "apps.common.dashboard.dashboard_callback",
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": "apps.common.dashboard.sidebar_navigation",
    },
}

EXPOSE_CLIENT_IDENT = env("EXPOSE_CLIENT_IDENT")


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "apps": {"handlers": ["console"], "level": "DEBUG",
                 "propagate": False},
    },
}
