ARG BUILD_FROM
FROM ${BUILD_FROM}

# ---- Runtime-Pakete (bleiben im Image) ----
RUN apk add --no-cache \
      python3 py3-pip socat \
      openssl libffi

# ---- Build-Dependencies (werden später entfernt) ----
RUN apk add --no-cache --virtual .build-deps \
      build-base python3-dev libffi-dev openssl-dev cargo make

# ---- Virtuelle Umgebung (PEP 668-konform) ----
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# ---- App-Dateien ----
WORKDIR /app
COPY requirements.txt /app/
COPY app/ /app/

# ---- Pip-Tools updaten & Requirements installieren ----
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install -r /app/requirements.txt

# ---- Build-Dependencies entfernen ----
RUN apk del .build-deps

# ---- s6-Services einspielen ----
COPY rootfs/ /
RUN chmod +x /etc/services.d/austrian-dsmr-mqtt/run

# Wichtig: KEIN CMD/ENTRYPOINT setzen (Base-Image startet /init selbst)

RUN echo "=== LIST /etc/services.d ===" \
 && ls -l /etc/services.d \
 && echo "=== LIST austrian-dsmr-mqtt ===" \
 && ls -l /etc/services.d/austrian-dsmr-mqtt \
 && echo "=== HEAD run ===" \
 && head -n 3 /etc/services.d/austrian-dsmr-mqtt/run | sed -n '1,3p' | od -c

