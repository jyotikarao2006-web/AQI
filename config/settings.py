import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = ["django.contrib.staticfiles", "forecast"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
}]
DATABASES = {}  # no database needed: the app only serves model predictions
STATIC_URL = "static/"
USE_TZ = True

# --- Model settings -------------------------------------------------------
MODEL_DIR = BASE_DIR / "ml_models"
# False: the LSTM output at step t is the AQI *for* step t (same-step estimate).
# True : the LSTM output at step t is the AQI for step t+1 (next-step forecast).
# Set this to match how you built y during training.
LSTM_TARGET_IS_NEXT_STEP = False
# Used only when ml_models/lstm_y_scaler.pkl is missing AND the LSTM output looks scaled (0-1).
# Maps the output back as out * (hi - lo) + lo. Set to the min/max AQI you trained on, or None to disable.
LSTM_OUTPUT_RANGE = (0, 500)

# --- Live data (Open-Meteo) -----------------------------------------------
# Timezone used when asking Open-Meteo for "the last 24 hours" is fixed to Asia/Kolkata in
# forecast/openmeteo.py. Nothing to configure: the API is free and needs no key.
# Logging: show Open-Meteo problems in the runserver console.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"forecast": {"handlers": ["console"], "level": "INFO"}},
}
