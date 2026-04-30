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

# --timeout 180 = give LLM-bound requests up to 3 minutes before the
# worker is killed. Default gunicorn timeout is 30s; rubric grading on a
# real PR diff regularly takes 30-60s end-to-end (diff fetch + Sonnet 4
# inference + Django persist), and the response handler that flips
# GradingSession from drafting → drafted runs AFTER the LLM returns.
# At 30s, gunicorn kills the worker mid-LLM-call, the response never
# reaches Django, and the session is stranded in `drafting` forever.
#
# 180s is generous headroom; it's a tactical fix until v1.1 moves the
# grading kickoff into a Celery/RQ background worker, after which this
# timeout becomes irrelevant (HTTP requests will return in <1s).
CMD ["gunicorn", "reviewhub.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "180"]
