# LogistikoCRM — multi-stage build
#
# Stages:
#   frontend → build του React (Vite) frontend
#   app      → Django + gunicorn (default για web/celery/beat)
#   nginx    → nginx με τα static + το built frontend (production)
#
# Χρήση: docker compose -f docker-compose.prod.yml up -d --build

# ---------- Stage 1: React frontend build ----------
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: Django application ----------
FROM python:3.11-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# postgresql-client: pg_dump για backups | libmagic1: έλεγχος τύπου αρχείων
#
# Ο postgresql-client καρφώνεται στο major του server (postgres:15 στο
# docker-compose.prod.yml) μέσω του PGDG repo: ο client της βάσης του
# Debian (trixie => v17) παράγει dumps με v17 SETs (π.χ.
# transaction_timeout) που το pg_restore ΔΕΝ μπορεί να επαναφέρει σε
# server 15 — δηλαδή backups που γράφονται «επιτυχώς» αλλά είναι
# μη-επαναφέρσιμα. Tests: DockerPgClientServerParityTest + CI
# docker-build step. Αν αναβαθμιστεί ο server, αλλάξτε ΚΑΙ τα δύο.
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    gettext \
    libmagic1 \
    && install -d /usr/share/postgresql-common/pgdg \
    && python -c "import urllib.request; urllib.request.urlretrieve('https://www.postgresql.org/media/keys/ACCC4CF8.asc', '/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc')" \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y postgresql-client-15 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

RUN mkdir -p logs media static backups

# Μη-root χρήστης: περιορίζει τη ζημιά σε περίπτωση RCE/container escape
RUN useradd --create-home --shell /usr/sbin/nologin app \
    && chown -R app:app /app
USER app

# Collect static files (dummy env — δεν χρειάζεται βάση/secret για static).
# ΠΡΕΠΕΙ να τρέχει ΜΕΤΑ το USER app: το django.setup() δημιουργεί tendo
# singleton lockfiles στο /tmp (Massmail/Reminder/MonthlySnapshotSaving)
# — αν τρέξει ως root, ψήνονται root-owned μέσα στο image και ΚΑΘΕ
# runtime process του μη-root user σκάει με PermissionError (crash loop).
# Το rm καθαρίζει τα build-time locks ώστε να μη μείνουν στο image.
RUN SECRET_KEY=build-only DEBUG=True python manage.py collectstatic --noinput \
    && rm -f /tmp/*.lock

EXPOSE 8000

CMD ["gunicorn", "webcrm.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]

# ---------- Stage 3: nginx (production web server) ----------
FROM nginx:1.27-alpine AS nginx
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf
# Built React SPA
COPY --from=frontend /frontend/dist /usr/share/nginx/html
# Django static files (admin, CRM templates κλπ)
COPY --from=app /app/static /var/www/static
