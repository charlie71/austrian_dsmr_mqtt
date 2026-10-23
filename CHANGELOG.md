# Changelog

## 1.3.0 (2026-10-23)

- **15-Minuten-Leistung nach Zählerzeit** (Option `LEISTUNG_15MIN`, Standard an): Viertelstundengrenzen
  nach der Uhr des Zählers (UTC), Zählerstand an der Grenze zwischen den Telegrammen interpoliert.
  - `Smartmeter/p15/intervall` (retained, je Viertelstunde): Beginn, Ende, Energie, mittlere Leistung,
    Gültigkeit, Qualität (`exakt`/`interpoliert`/`naeherung`/`ungueltig`) und Grund.
  - `Smartmeter/p15/laufend` (je Telegramm): Energie bisher, Mittelwert bisher, Prognose für das
    Intervallende (Energie bisher + aktuelle Leistung × Restzeit).
  - Sensoren „15min Leistung“ (`sensor.stromzaehler_15min_leistung`), „15min Prognose“
    (`sensor.stromzaehler_15min_prognose`), „15min Bezug laufend“ (`sensor.stromzaehler_15min_bezug_laufend`).
  - Ungültig: App-Start im Intervall, Datenlücke > 120 s an einer Grenze, Zählerstand gefallen,
    Wert über der Plausibilitätsgrenze `MAX_LEISTUNG_KW` (Standard 17,3 kW).
- Ausschalten der Option entfernt die drei Sensoren wieder aus Home Assistant.
- **Einheitliche Entity-IDs** `sensor.stromzaehler_*` für Neuinstallationen (`default_entity_id`):
  Bezug/Einspeisung gesamt → `…_energie_bezug`/`…_energie_einspeisung`, aktuell →
  `…_leistung_bezug`/`…_leistung_einspeisung`, Zählerzeit → `…_zaehlerzeit`. Die `unique_id`s bleiben;
  bestehende Entitäten werden in Home Assistant umbenannt (Verlauf bleibt erhalten).

## 1.2.2 (2026-10-23)

- **Alle Zählerwerte als Entitäten:** MQTT-Discovery für die 14 übrigen Werte des T210-D-R
  (`sensor.stromzaehler_*`): Bezug/Einspeisung je Tarif, Blindenergie gesamt und je Tarif,
  Blindleistung, Zählerzeit und P1-Version (die beiden letzten als Diagnose).
  Die vier bisherigen Sensoren bleiben unverändert.
- **App-Icon und Logo** (`icon.png`, `logo.png`) für den App-Store in Home Assistant.

## 1.2.1 (2026-10-23)

- **Integrität:** GCM-Tag-Prüfung funktioniert jetzt mit dem GAK, wie ihn der Netzbetreiber liefert
  (16 Byte). Das Security-Control-Byte (`30`) aus dem Telegramm wird automatisch vorangestellt;
  ein bereits mit `30` eingetragener Wert (17 Byte) funktioniert weiterhin.
- Hat die Prüfung einmal funktioniert, werden Telegramme mit falschem Tag verworfen statt veröffentlicht.

## 1.2.0 (2026-10-23)

- **Build:** Basisimage `ghcr.io/home-assistant/base:latest` als Standard im Dockerfile (Supervisor ab 2026.04 setzt `BUILD_FROM` nicht mehr); veraltete Architekturen `armv7`/`i386` entfernt.
- **Image-Größe:** Installation in einer Docker-Schicht, Build-Werkzeuge werden im selben Schritt wieder entfernt; ungenutzte Pakete (`socat`, `py3-pip`, `openssl`, `libffi`) und pip im venv entfallen.
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
