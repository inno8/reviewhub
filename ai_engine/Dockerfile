# Pin Debian Bookworm explicitly. Docker Hub's `python:3.12-slim` tag
# was rolled forward to Debian 13 Trixie in early 2026; Trixie's apt
# ships PHP 8.4 and the `php8.2-*` packages no longer resolve. Keeping
# Bookworm preserves the PHP 8.2 LTS line that our deterministic
# runners expect (security support runs through end-2025; the
# corresponding bookworm-slim base will keep getting security updates
# into 2028 via Debian LTS).
FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# PHP tooling for deterministic analysis (PHP Workstream).
# Bookworm ships PHP 8.2 in apt directly. phpcs + phpstan are
# installed globally via composer so they're on PATH.
#
# php8.2-zip + unzip are required for composer's package downloader.
# Without either, `composer require` fails with:
#   In ZipDownloader.php line 81:
#     The zip extension and unzip/7z commands are both missing, skipping.
RUN apt-get update && apt-get install -y --no-install-recommends \
    php8.2-cli \
    php8.2-xml \
    php8.2-mbstring \
    php8.2-zip \
    unzip \
    composer \
    && rm -rf /var/lib/apt/lists/*

RUN composer global require \
    squizlabs/php_codesniffer:^3.9 \
    phpstan/phpstan:^1.11 \
    --no-interaction
ENV PATH="/root/.composer/vendor/bin:${PATH}"

COPY . .

EXPOSE 8001

# Entry point lives at top-level main.py (which imports from app/api/*).
# Earlier scaffolds had main.py inside app/, hence the legacy "app.main:app"
# reference — that path no longer exists and breaks ImportError-on-boot.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
