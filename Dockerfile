FROM python:3.13-alpine

LABEL org.opencontainers.image.source="https://github.com/Moritz455/studip-sync"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Europe/Berlin \
    STUDIP_CONFIG_FILE=/app/.config/config.json \
    CRON_INTERVAL="0 8,13,19 * * *"

# Install runtime and build dependencies for lxml and certificates
RUN apk add --no-cache \
    tzdata \
    ca-certificates \
    libxml2 \
    libxslt \
    && apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    libxml2-dev \
    libxslt-dev \
    libffi-dev

WORKDIR /app

# Copy dependency definition and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps

# Copy application files
COPY . .

# Set execution permissions
RUN chmod +x entrypoint.sh studip_sync.py scripts/studip-sync

# Create directories for config and files
RUN mkdir -p /app/.config /app/studip_files

# Define mount points
VOLUME ["/app/.config", "/app/studip_files"]

ENTRYPOINT ["/app/entrypoint.sh"]
