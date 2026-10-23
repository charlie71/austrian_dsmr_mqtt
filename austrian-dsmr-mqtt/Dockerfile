# Seit Supervisor 2026.04 wird BUILD_FROM nicht mehr gesetzt.
# Multi-Arch-Basisimage als Standard; aeltere Supervisor koennen es weiterhin ueberschreiben.
ARG BUILD_FROM=ghcr.io/home-assistant/base:latest
FROM ${BUILD_FROM}

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt /tmp/requirements.txt

# Alles in EINER Schicht: Build-Werkzeuge werden nur gebraucht, falls pip fuer ein
# Paket kein fertiges Wheel findet, und im selben Schritt wieder entfernt.
# (Stehen sie in einer eigenen Schicht, bleiben sie trotz "apk del" im Image.)
RUN apk add --no-cache python3 \
 && apk add --no-cache --virtual .build-deps \
      build-base python3-dev libffi-dev openssl-dev \
 && python3 -m venv /opt/venv \
 && pip install --prefer-binary -r /tmp/requirements.txt \
 && apk del .build-deps \
 && { pip uninstall -y pip setuptools wheel >/dev/null 2>&1 || true; } \
 && find /opt/venv -depth \( -name '__pycache__' -o -name 'tests' -o -name 'test' \) \
      -type d -exec rm -rf {} + \
 && rm -rf /tmp/requirements.txt /root/.cache

WORKDIR /app
COPY app/ /app/
COPY rootfs/ /
RUN chmod +x /etc/services.d/austrian-dsmr-mqtt/run

# Wichtig: KEIN CMD/ENTRYPOINT setzen (Base-Image startet /init selbst)
