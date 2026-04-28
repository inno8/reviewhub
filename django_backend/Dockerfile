# Pin Debian Bookworm to match the ai-engine base (Trixie rollover early
# 2026 broke ai-engine's PHP 8.2 packages; keeping both services on the
# same Debian release means a uniform glibc + system-library surface).
FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8000

CMD ["gunicorn", "reviewhub.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
