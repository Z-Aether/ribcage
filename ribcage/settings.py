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

# Nothing forwarded by the proxy is read: outside DEBUG, EveryRequestIsHttps sets the scheme (#31, #54).
SECURE_PROXY_SSL_HEADER = None
USE_X_FORWARDED_HOST = False
USE_X_FORWARDED_PORT = False
SECURE_HSTS_SECONDS = 365 * 24 * 60 * 60
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
SECURE_SSL_REDIRECT = False
# The proxy redirects to https, and preload would commit the host's apex domain, so both warnings are decided (#16).
# auth.W004 cannot see the case-insensitive unique constraint on Lower(display_name) (#69).
SILENCED_SYSTEM_CHECKS = ["security.W008", "security.W021", "auth.W004"]
# Secure with DEBUG on or off; over local http only Chromium and Firefox keep them, at localhost or 127.0.0.1 (#31).
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
# Scripts can't read this cookie, so htmx requests must take the token from the page, e.g. hx-headers (#16).
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "ribcage.identity",
    "ribcage.films",
    "ribcage.hello",
    "ribcage.seeding",
    "ribcage.gallery",
]

MIDDLEWARE = [
    "ribcage.https.EveryRequestIsHttps",
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
        # WAL on every connection (#14, #52); IMMEDIATE and a timeout make simultaneous writers queue, not fail (#14).
        "OPTIONS": {"init_command": "PRAGMA journal_mode=WAL;", "transaction_mode": "IMMEDIATE", "timeout": 20},
    }
}

AUTH_USER_MODEL = "identity.Voter"
AUTHENTICATION_BACKENDS = ["ribcage.identity.backends.DisplayNameBackend"]

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

# With DEBUG off Django only mails request errors to the empty ADMINS; log them to stderr instead (#51).
# The message is "Internal Server Error: <path>" and the traceback: no headers, no client address (#31).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(message)s"}},
    "handlers": {"stderr": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "loggers": {"django.request": {"handlers": ["stderr"], "level": "ERROR", "propagate": False}},
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
# A collapsed film card trims every note to this many characters, with an ellipsis (#21, #39).
NOTE_TRIM_LENGTH = environment.positive_whole_number("NOTE_TRIM_LENGTH", default=120)
