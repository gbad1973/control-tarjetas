
import os
from pathlib import Path
from decouple import config, Csv
import dj_database_url
from dotenv import load_dotenv

# ========== CARGAR VARIABLES DE ENTORNO ==========
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# ========== BASE DEL PROYECTO ==========
BASE_DIR = Path(__file__).resolve().parent.parent

# ========== SEGURIDAD BÁSICA ==========
SECRET_KEY = config('SECRET_KEY', default='reemplaza-esto-en-produccion')
DEBUG = config('DEBUG', default=False, cast=bool)  # En producción debe ser False
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*", cast=Csv())

# ========== CSRF Y ORÍGENES CONFIABLES (para Render) ==========
CSRF_TRUSTED_ORIGINS = [
    'https://control-tarjetas.onrender.com',
    'http://control-tarjetas.onrender.com',
]

# ========== APLICACIONES ==========
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'tarjetas_app',
    'django.contrib.humanize',
]

# ========== MIDDLEWARE ==========
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Para archivos estáticos en producción
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ========== URLs y WSGI ==========
ROOT_URLCONF = 'controltarjetas.urls'
WSGI_APPLICATION = 'controltarjetas.wsgi.application'

# ========== TEMPLATES ==========
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ========== BASE DE DATOS (PostgreSQL en Render) ==========
DATABASES = {
    'default': dj_database_url.parse(
        config('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=True  # Necesario para Neon
    )
}

# ========== VALIDACIÓN DE CONTRASEÑAS ==========
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ========== INTERNACIONALIZACIÓN ==========
LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True

# ========== ARCHIVOS ESTÁTICOS ==========
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ========== ARCHIVOS DE MEDIOS ==========
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ========== CLAVE PRIMARIA PREDETERMINADA ==========
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ========== URLs DE LOGIN ==========
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'

# ========== CONFIGURACIÓN DE PRODUCCIÓN (cuando DEBUG=False) ==========
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True