"""
Django settings for the Daladala Finder project.

DEVELOPMENT (your laptop): works with no setup. Uses SQLite (db.sqlite3) and DEBUG on.
                           Put DATABASE_URL in a .env file next to manage.py to use PostgreSQL.
DEPLOYMENT (a server):     set these environment variables (see .env.example):
    DJANGO_DEBUG=False
    DJANGO_SECRET_KEY=<a long random secret>
    DJANGO_ALLOWED_HOSTS=yourdomain.com
    DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME     -> uses PostgreSQL
"""
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file(path):
    """Read KEY=VALUE lines from a local .env file (if there is one) into the environment.
    Real environment variables win, so a server's settings are never overwritten."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(BASE_DIR / ".env")


def env_bool(name, default):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# ---------------------------------------------------------------- security
DEBUG = env_bool("DJANGO_DEBUG", True)

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-^vz+jo$i6)k+%j&c_sdw6s_x543+9lse0w+ddp%l(bt7=9w*^0",  # development only
)
if not DEBUG and SECRET_KEY.startswith("django-insecure"):
    raise RuntimeError("Set DJANGO_SECRET_KEY before running with DJANGO_DEBUG=False.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost" if DEBUG else "")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")   # e.g. https://yourdomain.com

# Render.com tells the app its web address; allow it automatically
RENDER_HOST = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_HOST:
    ALLOWED_HOSTS.append(RENDER_HOST)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_HOST}")


# ---------------------------------------------------------------- apps
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'accounts',
    'routes',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    # Picks English or Swahili: the EN/SW switch (cookie) first, then the browser's language
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # Every page needs login, except pages marked @login_not_required (login, sign up)
    'django.contrib.auth.middleware.LoginRequiredMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'daladala_finder.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'daladala_finder.wsgi.application'


# ---------------------------------------------------------------- database
# SQLite for development. PostgreSQL when DATABASE_URL is set (deployment).
def database_from_url(url):
    """Turn postgres://user:password@host:port/name into Django's DATABASES setting."""
    parts = urlparse(url)
    if parts.scheme not in ("postgres", "postgresql"):
        raise RuntimeError("DATABASE_URL must start with postgres://")
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': unquote(parts.path.lstrip("/")),
        'USER': unquote(parts.username or ""),
        'PASSWORD': unquote(parts.password or ""),
        'HOST': parts.hostname or "localhost",
        'PORT': str(parts.port or 5432),
        'CONN_MAX_AGE': 60,
        # Cloud databases like Neon add ?sslmode=require to the URL
        'OPTIONS': {'sslmode': os.environ.get("DATABASE_SSLMODE")
                    or parse_qs(parts.query).get("sslmode", ["prefer"])[0]},
    }


if os.environ.get("DATABASE_URL"):
    DATABASES = {'default': database_from_url(os.environ["DATABASE_URL"])}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# ---------------------------------------------------------------- login
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'routes:home'
LOGOUT_REDIRECT_URL = 'accounts:login'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

SESSION_COOKIE_AGE = 60 * 60 * 24 * 30      # stay logged in for 30 days


# ---------------------------------------------------------------- language & time
LANGUAGE_CODE = 'en'   # default when the browser asks for neither language
LANGUAGES = [
    ('en', 'English'),
    ('sw', 'Kiswahili'),
]
# Our Swahili text: locale/sw/LC_MESSAGES/django.po
# After editing it run: python manage.py compilemessages
LOCALE_PATHS = [BASE_DIR / 'locale']
TIME_ZONE = 'Africa/Dar_es_Salaam'
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------- static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'  # used when you deploy (collectstatic)

# Files people upload (profile photos) are kept in the database (accounts/storage.py),
# so they are not lost when free hosting like Render restarts and wipes its disk.
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'      # only used by the old on-disk photos (see move_photos_to_db)
STORAGES = {
    "default": {"BACKEND": "accounts.storage.DatabaseStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Show error messages in Bootstrap's red "danger" style
from django.contrib.messages import constants as message_constants  # noqa: E402
MESSAGE_TAGS = {message_constants.ERROR: 'danger'}

# On a server, WhiteNoise serves the CSS/JS/fonts (installed from requirements-prod.txt)
try:
    import whitenoise  # noqa: F401
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
    STORAGES["staticfiles"] = {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"}
except ImportError:
    pass

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Let the browser tell map servers which website is asking for map tiles.
# (Django's default "same-origin" hides it, and map servers like OpenStreetMap then block the requests.)
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"


# ---------------------------------------------------------------- extra safety when deployed
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "0"))   # raise once HTTPS works
