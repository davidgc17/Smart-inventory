"""
Django settings for smart_inventory project (desarrollo).
"""

from pathlib import Path
import os
from dotenv import load_dotenv
import dj_database_url

# ---------------------------------------------------------------------
# Base y .env
# ---------------------------------------------------------------------
load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret")
DEBUG = os.getenv("DEBUG", "True") == "True"

# Puedes dejarlo por .env (coma-separado) o usar el default de abajo
ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost,192.168.1.72"
).split(",")

# HTTPS dev por IP (si usas runserver_plus + mkcert). Añade tu IP real.
CSRF_TRUSTED_ORIGINS = [
    "https://192.168.1.72:8000",
    # "https://tu-dominio.com",  # producción
]

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/scan/'


# ---------------------------------------------------------------------
# Apps
# ---------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # 3rd party
    "rest_framework",
    "corsheaders",
    "django_extensions",   # útil en dev (runserver_plus, etc.)

    # Local
    "inventory",
]

# ---------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",      # CORS antes de CommonMiddleware
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# CORS abierto en desarrollo (restringe en producción)
CORS_ALLOW_ALL_ORIGINS = True
# En producción preferir: CORS_ALLOWED_ORIGINS = ["https://tu-frontend.com"]

# ---------------------------------------------------------------------
# URLs / WSGI
# ---------------------------------------------------------------------
ROOT_URLCONF = "smart_inventory.urls"
WSGI_APPLICATION = "smart_inventory.wsgi.application"

# ---------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Carpeta global de templates (además de las app/templates)
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

# ---------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.parse(
        os.getenv("DATABASE_URL", "sqlite:///db.sqlite3")
    )
}

# ---------------------------------------------------------------------
# Internacionalización
# ---------------------------------------------------------------------
LANGUAGE_CODE = "es-es"
TIME_ZONE = "Europe/Madrid"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------
# Static & Media
# ---------------------------------------------------------------------
# En dev puedes poner tus CSS/JS/imagenes en BASE_DIR/static
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]           # carpeta de trabajo (dev)
STATIC_ROOT = BASE_DIR / "staticfiles"             # salida de collectstatic (prod)

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
}

# ---------------------------------------------------------------------
# Seguridad (solo DEV). En producción deben ser True/activadas.
# ---------------------------------------------------------------------
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# ---------------------------------------------------------------------
# Django
# ---------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
