# Changelog

## 1.2.0 (2026-10-23)

- **Sicherheit:** MQTT-Passwort wird nicht mehr ins Log geschrieben.
- **MQTT-Discovery:** Gerät „Vorratsraum Stromzähler“ mit vier Sensoren; gleiche `unique_id` wie die bisherigen
  `mqtt.yaml`-Sensoren, damit Verlauf und Statistik erhalten bleiben (Option `DISCOVERY`).
- **Verfügbarkeit:** `Smartmeter/status` online/offline (retained, Last Will).
- **Robustheit:** serielle Schnittstelle wird bei Fehlern oder 60 s ohne gültiges Telegramm neu geöffnet;
  MQTT-Netzwerkschleife (`loop_start`) mit automatischem Wiederverbinden.
- **Integrität:** GCM-Tag wird geprüft (Fallback auf CRC-Prüfung des Telegramms, falls der Tag nicht passt).
- **Konfiguration:** gewählter serieller Port wird jetzt tatsächlich verwendet (bis 1.1.x immer `/dev/ttyUSB0`);
  `uart: true` statt fester Geräteliste.
- **Build:** Paketversionen festgelegt, ungenutztes `cryptography`/cargo entfernt; Parser wird nur einmal angelegt.
