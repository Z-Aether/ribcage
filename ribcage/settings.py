from pathlib import Path

from ribcage import environment

BASE_DIR = Path(__file__).resolve().parent.parent

# Everything that varies by deployment comes from the environment, and no secret has a default (#18, #45).
SECRET_KEY = environment.required("SECRET_KEY")
DEBUG = environment.flag("DEBUG", default=False)
ALLOWED_HOSTS = environment.required_list("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = environment.required_list("CSRF_TRUSTED_ORIGINS")
JOIN_CODE = environment.required("JOIN_CODE")
ADMIN_PASSWORD = environment.required("ADMIN_PASSWORD")
TMDB_API_KEY = environment.required("TMDB_API_KEY")
DTDD_API_KEY = environment.required("DTDD_API_KEY")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "ribcage.identity",
    "ribcage.hello",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ribcage.urls"
WSGI_APPLICATION = "ribcage.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "ribcage" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        # A relative path is taken from the repo root, so local runs work from any directory.
        "NAME": BASE_DIR / environment.required("DATABASE_PATH"),
    }
}

AUTH_USER_MODEL = "identity.Voter"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        # Voter has none of the default attributes, so compare against the display name (#37).
        "OPTIONS": {"user_attributes": ["display_name"]},
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
# The deployment's one wall-clock zone; devices' own zones are never used (#36).
TIME_ZONE = environment.required("TIME_ZONE")
USE_I18N = True
USE_TZ = True

# The app serves its own static files, so the image needs no second service (#14).
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "ribcage" / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Judgement values: tunable from the environment without a rebuild; correctness values stay hard-coded (#25).
# Each proposal in a batch differs from every other by at least this many films; remeasure, or fall back to 2 (#17).
DIVERSITY_CUT = environment.positive_whole_number("DIVERSITY_CUT", default=4)
# c in W = c·|floor set|: raising the floor one step is worth one rep point per person (#33).
FLOOR_WEIGHT_MULTIPLIER = environment.positive_whole_number("FLOOR_WEIGHT_MULTIPLIER", default=1)
# Proposals per batch: five fit side by side on a desktop, and "more" extends a batch (#17).
BATCH_SIZE = environment.positive_whole_number("BATCH_SIZE", default=5)
# RUN's clock runs on the device, so a 30–60 s poll carries only the admin's edits and phase moves (#13, #36).
POLL_INTERVAL_SECONDS = environment.positive_whole_number("POLL_INTERVAL_SECONDS", default=30)
# Yes votes a matched topic needs, beyond outnumbering its no votes, to show the trigger icon (#20).
TRIGGER_ICON_THRESHOLD = environment.positive_whole_number("TRIGGER_ICON_THRESHOLD", default=5)
# Login backoff: this many failures for one display name within the window bring a wait (#31).
LOGIN_BACKOFF_FAILURES = environment.positive_whole_number("LOGIN_BACKOFF_FAILURES", default=5)
LOGIN_BACKOFF_WINDOW_MINUTES = environment.positive_whole_number("LOGIN_BACKOFF_WINDOW_MINUTES", default=15)
LOGIN_BACKOFF_WAIT_MINUTES = environment.positive_whole_number("LOGIN_BACKOFF_WAIT_MINUTES", default=1)
