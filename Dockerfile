# Basis-Image mit Python
FROM python:3.10-slim

# Arbeitsverzeichnis erstellen
WORKDIR /app

# Systemabhängigkeiten installieren
RUN apt-get update && apt-get install -y \
    socat \
    && apt-get clean

# Abhängigkeiten und Projektdateien kopieren
COPY requirements.txt /app/
COPY . /app/

# Python-Abhängigkeiten installieren
RUN pip install --no-cache-dir -r requirements.txt

# Python-Ausgabe unbuffered
ENV PYTHONUNBUFFERED=1

# Startbefehl definieren
# CMD ["python3", "decrypt.py"]
# CMD ["python3", "decrypt.py", "$GUEK", "-a", "$GAK", "--serial-input-port", "$SERIAL_INPUT_PORT", "--mqtt-broker", "$MQTT_BROKER","--mqtt-user","$MQTT_USER","--mqtt-password","$MQTT_PASSWORD"]
CMD ["sh", "-c", "python3 decrypt.py $GUEK -a $GAK --serial-input-port $SERIAL_INPUT_PORT --mqtt-broker $MQTT_BROKER --mqtt-user $MQTT_USER --mqtt-password $MQTT_PASSWORD"]
