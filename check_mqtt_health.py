import os
import time

# Speicherort für den letzten Sendezeitpunkt
MQTT_LAST_SEND_FILE = "/tmp/mqtt_last_send"

# Prüfe, ob eine Datei mit dem letzten Sendezeitpunkt existiert
if not os.path.exists(MQTT_LAST_SEND_FILE):
    print("MQTT Healthcheck failed: No data sent")
    exit(1)

# Lese den letzten Sendezeitpunkt
with open(MQTT_LAST_SEND_FILE, "r") as f:
    last_send_time = float(f.read().strip())

# Prüfe, ob der letzte Sendezeitpunkt innerhalb von 30 Sekunden liegt
if time.time() - last_send_time > 30:
    print("MQTT Healthcheck failed: No data sent in the last 30 seconds")
    exit(1)

print("MQTT Healthcheck passed")
