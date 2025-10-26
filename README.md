# ⚡Austrian DSMR MQTT — Decrypter & Proxy (Sagemcom T210-D-R, Energie Steiermark)

*Home-Assistant Add-on zur Entschlüsselung und Weitergabe von DSMR-P1-Telegrammen per MQTT*

Dieses Projekt basiert auf dem ursprünglichen „Decrypter and proxy…“ und wurde zu einem **Home-Assistant Add-on** weiterentwickelt. Es entschlüsselt die verschlüsselten DSMR-P1-Telegramme (Energie Steiermark / Sagemcom T210-D-R) und publiziert die Messwerte via **MQTT**. Damit können die Daten bequem in Home Assistant, Node-RED, Grafana etc. verarbeitet werden.

---

## 🔍 Inhalt

* [Funktionen](#funktionen)
* [Voraussetzungen](#voraussetzungen)
* [Installation in Home Assistant](#installation-in-home-assistant)
* [Konfiguration des Add-ons](#konfiguration-des-add-ons)
* [MQTT-Topics & Beispiel](#mqtt-topics--beispiel)
* [Troubleshooting](#troubleshooting)
* [Manuelle Nutzung (ohne Home Assistant)](#manuelle-nutzung-ohne-home-assistant)
* [Ordnerstruktur dieses Repos](#ordnerstruktur-dieses-repos)
* [Lizenz & Sicherheitshinweise](#lizenz--sicherheitshinweise)
* [Quellen & weitere Infos](#quellen--weitere-infos)

---

## ⚙️ Funktionen

* Entschlüsselt DSMR-P1-Telegramme (Energie Steiermark, Sagemcom T210-D-R) mittels **GUEK** (Key) und **GAK/AAD**
* Liest seriell über **P1-Port → USB-Adapter** (z. B. FTDI) ein
* Publiziert die Werte als **MQTT-Topics** (EN-Namen aus `dsmr_parser`)
* Läuft als **Home-Assistant Add-on** (Backup-fähig, Start/Stop über Supervisor)
* Serielle Schnittstelle bequem per **Dropdown** wählbar

---

## Voraussetzungen

1. **Schlüssel anfordern**
   Bei **Energie Steiermark** die **Decryption Keys** anfragen:

   * **GUEK** (Global Unicast Encryption Key)
   * **GAK / AAD** (Global Authentication Key)
     (Die Freischaltung kann etwas dauern.)

2. **P1-Kabel / USB-Adapter**
   Ein P1/DSMR-Kabel mit USB-Seriell-Wandler (z. B. FTDI).
   Beispiel: „P1-Port Kabel für Sagemcom/ISKRA, 5 V TTL, FTDI“.

3. **MQTT-Broker**
   Z. B. **Mosquitto Add-on** in Home Assistant (`core-mosquitto`) oder externer Broker.

---

## 🧩 Installation in Home Assistant

### Variante A: Über öffentliches Add-on-Repository

1. In Home Assistant: **Einstellungen → Add-ons → Add-on-Store**
2. Oben rechts ** → Repositories**
3. Repository-URL eintragen (dein GitHub-Repo, z. B.):
   `https://github.com/charlie71/austrian_dsmr_mqtt`
4. In der Liste **„Austrian DSMR MQTT“** auswählen → **Installieren**

### Variante B: Lokal (Entwicklung / Test)

1. Auf dem HA-System den Ordner **`/addons_local/`** öffnen (Samba/SSH).
2. Den Add-on-Ordner `austrian-dsmr-mqtt` dorthin kopieren.
3. In HA: **Einstellungen → Add-ons → Add-on-Store → ⋮ → Lokale Add-ons neu laden**
4. Add-on installieren.

> **Tipp:** Nach Updates die Versionsnummer in `config.json` erhöhen und „Lokale Add-ons neu laden“, damit der Supervisor neu baut.

---

## ⚙️ Konfiguration des Add-ons

Öffne das Add-on → **Konfiguration**. Felder:

| Feld                | Beschreibung                                     | Beispiel                      |
| ------------------- | ------------------------------------------------ | ----------------------------- |
| `GUEK`              | Global Unicast Encryption Key (von E-Steiermark) | `…`                           |
| `GAK`               | Global Authentication Key (AAD)                  | `…`                           |
| `MQTT_BROKER`       | Hostname/IP des Brokers                          | `core-mosquitto`              |
| `MQTT_USER`         | MQTT-Benutzername                                | `mqtt`                        |
| `MQTT_PASSWORD`     | MQTT-Passwort                                    | `••••`                        |
| `SERIAL_INPUT_PORT` | Serielle Schnittstelle (Dropdown)                | `/dev/serial/by-id/usb-FTDI…` |

Weitere Hinweise:

* Die serielle Schnittstelle wird im UI als **Combobox** angeboten.
* Das Add-on nutzt `/data` für persistente Daten (Backup-fähig).
* Standard-Port-Einstellungen des P1-Ports werden intern gesetzt; keine weitere UART-Konfiguration im Add-on nötig.

Starten → **Protokolle** prüfen. Bei erfolgreichem Start werden MQTT-Nachrichten veröffentlicht.

---

## MQTT-Topics & Beispiel

* **Topic-Prefix:** `Smartmeter`
* Für jedes Feld (EN-Name lt. `dsmr_parser`) wird unter `Smartmeter/<EN_NAME>` publiziert, z. B.:

```
Smartmeter/P1_MESSAGE_HEADER           50
Smartmeter/P1_MESSAGE_TIMESTAMP        2025-10-25 18:09:12+00:00
Smartmeter/ELECTRICITY_IMPORTED_TOTAL  15382794
Smartmeter/CURRENT_ELECTRICITY_USAGE   466
Smartmeter/CURRENT_ELECTRICITY_DELIVERY 0
```

> Hinweis: Es wird **keine** MQTT-Autodiscovery für HA-Sensoren angelegt (bewusst simpel gehalten).
> Wer Autodiscovery möchte, kann per Node-RED oder MQTT-Automationen eigene Sensoren anlegen.

---

## 🧰 Troubleshooting

**Keine Daten via MQTT**

* `MQTT_BROKER`, `MQTT_USER`, `MQTT_PASSWORD` prüfen.
* Prüfen, ob im Log Entschlüsselung/Parsing läuft.
* Mit MQTT-Client (z. B. MQTT Explorer) Topic `Smartmeter/#` abonnieren.

**Serieller Port fehlt in der Liste**

* Ist das P1-Kabel korrekt verbunden/eingesteckt?
* Im HA-Host (Supervisor Terminal) `ls -l /dev/serial/by-id/` prüfen.
* Eventuell Neustart von HA-Host.

---

## Manuelle Nutzung (ohne Home Assistant)

Für reine CLI-Tests (z. B. auf einem Linux-Host):

```bash
python3 decrypt.py GUEK -a GAK \
  --serial-input-port /dev/ttyUSB0 \
  --mqtt-broker <BROKER> \
  --mqtt-user <USER> \
  --mqtt-password <PWD>
```

* **CTRL+C** beendet.
* Ohne MQTT-Parameter werden die entschlüsselten Telegramme auf STDOUT ausgegeben.
* Unter Home Assistant übernimmt das Add-on diese Aufrufe automatisch.

---

## Ordnerstruktur dieses Repos

```text
ha-addons/
├─ repository.json                # Metadaten fürs Add-on-Repository
├─ README.md                      # (diese Datei)
└─ austrian-dsmr-mqtt/            # Add-on
   ├─ config.json
   ├─ Dockerfile
   ├─ requirements.txt
   ├─ README.md                   # Add-on-spezifische Kurzanleitung (optional)
   ├─ translations/               # UI-Texte (optional)
   │  └─ de.yaml
   └─ rootfs/
      └─ etc/
         └─ services.d/
            └─ austrian-dsmr-mqtt/
               └─ run
```

> Wenn du dieses Repo als **Add-on-Repository** in Home Assistant einträgst, taucht das Add-on automatisch im Store auf.

---

## 🧾 Lizenz

Dieses Projekt steht unter der **MIT-Lizenz**.
Siehe [LICENSE](LICENSE).

---

## 🙌 Quellen & weitere Infos

* [dsmr_parser](https://github.com/ndokter/dsmr_parser) – Bibliothek zur Auswertung von DSMR-Telegrammen
* [DSMR Reader](http://dsmr-reader.readthedocs.io/en/latest/) – Stand-alone Lösung zum Loggen/Visualisieren
* P1-Spezifikationen:

  * [E-Netze AT: Kundenschnittstelle Smart Meter (PDF)](https://www.e-netze.at/downloads-data/pdf.aspx?pdf=EN_Update%20Kundenschnittstelle%20Smart%20Meter%20(03_2024)_WEB_RGB.pdf)
  * [CREOS Smarty (LU) P1 Spec (PDF)](https://smarty.creos.net/wp-content/uploads/P1PortSpecification.pdf)

