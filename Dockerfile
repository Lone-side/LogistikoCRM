# LogistikoCRM — multi-stage build
#
# Stages:
#   frontend → build του React (Vite) frontend
#   app      → Django + gunicorn (default για web/celery/beat)
#   nginx    → nginx με τα static + το built frontend (production)
#
# Χρήση: docker compose -f docker-compose.prod.yml up -d --build

# ---------- Stage 1: React frontend build ----------
FROM node:20-alpine AS frontend
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
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    gettext \
    libmagic1 \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

RUN mkdir -p logs media static backups

# Collect static files (dummy env — δεν χρειάζεται βάση/secret για static)
RUN SECRET_KEY=build-only DEBUG=True python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "webcrm.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]

# ---------- Stage 3: nginx (production web server) ----------
FROM nginx:1.27-alpine AS nginx
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf
# Built React SPA
COPY --from=frontend /frontend/dist /usr/share/nginx/html
# Django static files (admin, CRM templates κλπ)
COPY --from=app /app/static /var/www/static
