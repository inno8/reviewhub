FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# PHP tooling for deterministic analysis (PHP Workstream).
# python:3.12-slim is Debian 12 Bookworm which ships PHP 8.2 in apt directly.
# phpcs is installed globally via composer so `phpcs` is on PATH.
RUN apt-get update && apt-get install -y --no-install-recommends \
    php8.2-cli \
    php8.2-xml \
    php8.2-mbstring \
    composer \
    && rm -rf /var/lib/apt/lists/*

RUN composer global require squizlabs/php_codesniffer:^3.9 --no-interaction
ENV PATH="/root/.composer/vendor/bin:${PATH}"

COPY . .

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
