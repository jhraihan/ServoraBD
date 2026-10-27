from .base import *
from .base import env

DEBUG = False

RENDER_EXTERNAL_HOSTNAME = env("RENDER_EXTERNAL_HOSTNAME", default="")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS = list(ALLOWED_HOSTS) + [RENDER_EXTERNAL_HOSTNAME]
    CSRF_TRUSTED_ORIGINS_EXTRA = ["https://" + RENDER_EXTERNAL_HOSTNAME]
else:
    CSRF_TRUSTED_ORIGINS_EXTRA = []

EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@servorabd.local")

if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"

OTP_ECHO_TO_LOG = False

MIDDLEWARE = list(MIDDLEWARE)
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
    "whitenoise.middleware.WhiteNoiseMiddleware",
)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "servorabd_cache",
        "OPTIONS": {"MAX_ENTRIES": 50000},
    },
}

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "private": {"BACKEND": "apps.common.storage.PrivateMediaStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

if env("USE_OBJECT_STORAGE") and env("S3_BUCKET_NAME", default=""):
    _S3 = {
        "endpoint_url": env("S3_ENDPOINT_URL"),
        "access_key": env("S3_ACCESS_KEY_ID"),
        "secret_key": env("S3_SECRET_ACCESS_KEY"),
        "bucket_name": env("S3_BUCKET_NAME"),
        "region_name": env("S3_REGION", default="auto"),
        "file_overwrite": False,
    }

    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {**_S3, "location": "media", "querystring_auth": False,
                    "custom_domain": env("S3_PUBLIC_DOMAIN", default=None)},
    }
    STORAGES["private"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {**_S3, "location": "private", "querystring_auth": True,
                    "querystring_expire": 300, "custom_domain": False},
    }

SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = (env.list("CSRF_TRUSTED_ORIGINS", default=[])
                        + CSRF_TRUSTED_ORIGINS_EXTRA)

X_FRAME_OPTIONS = "DENY"
