# The host is x86-64: build with --platform linux/amd64; the tag scheme is in CLAUDE.md (#43, #40).
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# The app runs unprivileged; /data is where it may write, so a fresh volume mounted there inherits the owner.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin ribcage \
    && install -d -o ribcage -g ribcage /data

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

COPY manage.py .
COPY ribcage ribcage

# Settings demand every variable, so collectstatic gets throwaway values inline; ENV would bake them in (#51).
RUN SECRET_KEY=collectstatic-only DEBUG=false ALLOWED_HOSTS=collectstatic.invalid \
    CSRF_TRUSTED_ORIGINS=https://collectstatic.invalid DATABASE_PATH=/data/collectstatic-only.sqlite3 \
    TIME_ZONE=UTC JOIN_CODE=collectstatic-only ADMIN_PASSWORD=collectstatic-only \
    TMDB_API_KEY=collectstatic-only DTDD_API_KEY=collectstatic-only \
    python manage.py collectstatic --noinput --verbosity 0

USER ribcage
# Plain HTTP on 8000, the port the host's proxy forwards to; the container publishes none on the host (#31, #43).
EXPOSE 8000
# A few sync workers, each serving one request at a time (#14); preload fails startup once, before listening, on a bad env.
# The log keeps time, request line, status and duration only: no client address, so never X-Forwarded-For (#31).
CMD ["gunicorn", "ribcage.wsgi", "--bind", "0.0.0.0:8000", "--workers", "3", "--preload", "--no-control-socket", \
     "--access-logfile", "-", "--access-logformat", "%(t)s \"%(r)s\" %(s)s %(M)sms"]
