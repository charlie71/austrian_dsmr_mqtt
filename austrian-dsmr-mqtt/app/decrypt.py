#!/usr/bin/env python
import serial
import binascii
import argparse
import paho.mqtt.client as mqtt
from Cryptodome.Cipher import AES
from traceback import print_exc
import sys
import time
import json
import os

APP_VERSION = "1.2.2"

# MQTT-Topics
TOPIC_PREFIX = "Smartmeter"
STATUS_TOPIC = TOPIC_PREFIX + "/status"          # online / offline (Last Will)

# Home-Assistant-MQTT-Discovery.
# WICHTIG: unique_id und default_entity_id entsprechen den bisherigen Sensoren aus mqtt.yaml,
# damit HA nach der Umstellung denselben Registry-Eintrag weiterverwendet (Verlauf, Statistik,
# InfluxDB, Energie-Dashboard bleiben erhalten). Einheiten/state_class daher nicht ändern!
DISCOVERY_SENSORS = [
    {"key": "ELECTRICITY_IMPORTED_TOTAL", "unique_id": "EG_xx_XX_electricity_imported_total",
     "default_entity_id": "sensor.total_imported_electical_energy", "name": "Bezug gesamt",
     "unit": "Wh", "device_class": "energy", "state_class": "total", "icon": "mdi:transmission-tower-export"},
    {"key": "ELECTRICITY_EXPORTED_TOTAL", "unique_id": "EG_xx_XX_electricity_exported_total",
     "default_entity_id": "sensor.total_exported_electical_energy", "name": "Einspeisung gesamt",
     "unit": "Wh", "device_class": "energy", "state_class": "total", "icon": "mdi:transmission-tower-import"},
    {"key": "CURRENT_ELECTRICITY_USAGE", "unique_id": "EG_xx_XX_current_electricity_usage",
     "default_entity_id": "sensor.current_electricity_usage", "name": "Bezug aktuell",
     "unit": "W", "device_class": "power", "state_class": None, "icon": "mdi:gauge"},
    {"key": "CURRENT_ELECTRICITY_DELIVERY", "unique_id": "EG_xx_XX_current_electricity_delivery",
     "default_entity_id": "sensor.current_electricity_delivery", "name": "Einspeisung aktuell",
     "unit": "W", "device_class": "power", "state_class": None, "icon": "mdi:gauge"},
]

def _s(key, eid, name, unit, dc, sc, icon, cat=None):
    return {"key": key, "unique_id": f"austrian_dsmr_mqtt_{eid}", "default_entity_id": f"sensor.stromzaehler_{eid}",
            "name": name, "unit": unit, "device_class": dc, "state_class": sc, "icon": icon, "entity_category": cat}

# Ab 1.2.2: alle übrigen Werte des T210-D-R (unique_id neu, Entity-IDs sensor.stromzaehler_*)
DISCOVERY_SENSORS += [
    _s("ELECTRICITY_USED_TARIFF_1", "energie_bezug_tarif_1", "Bezug Tarif 1", "Wh", "energy", "total", "mdi:transmission-tower-export"),
    _s("ELECTRICITY_USED_TARIFF_2", "energie_bezug_tarif_2", "Bezug Tarif 2", "Wh", "energy", "total", "mdi:transmission-tower-export"),
    _s("ELECTRICITY_DELIVERED_TARIFF_1", "energie_einspeisung_tarif_1", "Einspeisung Tarif 1", "Wh", "energy", "total", "mdi:transmission-tower-import"),
    _s("ELECTRICITY_DELIVERED_TARIFF_2", "energie_einspeisung_tarif_2", "Einspeisung Tarif 2", "Wh", "energy", "total", "mdi:transmission-tower-import"),
    _s("ELECTRICITY_REACTIVE_IMPORTED_TOTAL", "blindenergie_bezug", "Blindenergie Bezug", "varh", "reactive_energy", "total", "mdi:sine-wave"),
    _s("ELECTRICITY_REACTIVE_IMPORTED_TARIFF_1", "blindenergie_bezug_tarif_1", "Blindenergie Bezug Tarif 1", "varh", "reactive_energy", "total", "mdi:sine-wave"),
    _s("ELECTRICITY_REACTIVE_IMPORTED_TARIFF_2", "blindenergie_bezug_tarif_2", "Blindenergie Bezug Tarif 2", "varh", "reactive_energy", "total", "mdi:sine-wave"),
    _s("ELECTRICITY_REACTIVE_EXPORTED_TOTAL", "blindenergie_lieferung", "Blindenergie Lieferung", "varh", "reactive_energy", "total", "mdi:sine-wave"),
    _s("ELECTRICITY_REACTIVE_EXPORTED_TARIFF_1", "blindenergie_lieferung_tarif_1", "Blindenergie Lieferung Tarif 1", "varh", "reactive_energy", "total", "mdi:sine-wave"),
    _s("ELECTRICITY_REACTIVE_EXPORTED_TARIFF_2", "blindenergie_lieferung_tarif_2", "Blindenergie Lieferung Tarif 2", "varh", "reactive_energy", "total", "mdi:sine-wave"),
    _s("CURRENT_REACTIVE_IMPORTED", "blindleistung_bezug", "Blindleistung Bezug", "var", "reactive_power", "measurement", "mdi:sine-wave"),
    _s("CURRENT_REACTIVE_EXPORTED", "blindleistung_lieferung", "Blindleistung Lieferung", "var", "reactive_power", "measurement", "mdi:sine-wave"),
    _s("P1_MESSAGE_TIMESTAMP", "zeitstempel", "Zählerzeit", None, "timestamp", None, "mdi:clock-outline", "diagnostic"),
    _s("P1_MESSAGE_HEADER", "p1_version", "P1-Version", None, None, None, "mdi:information-outline", "diagnostic"),
]
DEVICE = {
    "identifiers": ["austrian_dsmr_mqtt_smartmeter"],
    "name": "Vorratsraum Stromzähler",
    "manufacturer": "Sagemcom",
    "model": "T210-D-R",
    "sw_version": APP_VERSION,
    "suggested_area": "Vorratsraum",
}
ORIGIN = {"name": "Austrian DSMR MQTT", "sw_version": APP_VERSION,
          "support_url": "https://github.com/charlie71/austrian_dsmr_mqtt"}

# Ohne gültiges Telegramm so lange -> Status offline + serielle Schnittstelle neu öffnen
NO_DATA_TIMEOUT_S = 60

# Standardausgaben explizit umleiten
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__

# DSMR parsing
has_dsmr_parser = True
try:
    from dsmr_parser import telegram_specifications
    from dsmr_parser.parsers import TelegramParser

    from dsmr_parser import obis_references
    # import dsmr_parser.obis_name_mapping

    print("Using DSMR parser")
except ImportError:
    has_dsmr_parser = False
    print("No DSMR parser found")

class SmartyProxy():
    def __init__(self):
        # Constants that describe the individual steps of the state machine:

        # Initial state. Input is ignored until start byte is detected.
        self.STATE_IGNORING = 0
        # Start byte (hex "DB") has been detected.
        self.STATE_STARTED = 1
        # Length of system title has been read.
        self.STATE_HAS_SYSTEM_TITLE_LENGTH = 2
        # System title has been read.
        self.STATE_HAS_SYSTEM_TITLE = 3
        # Additional byte after the system title has been read.
        self.STATE_HAS_SYSTEM_TITLE_SUFFIX = 4
        # Length of remaining data has been read.
        self.STATE_HAS_DATA_LENGTH = 5
        # Additional byte after the remaining data length has been read.
        self.STATE_HAS_SEPARATOR = 6
        # Frame counter has been read.
        self.STATE_HAS_FRAME_COUNTER = 7
        # Payload has been read.
        self.STATE_HAS_PAYLOAD = 8
        # GCM tag has been read.
        self.STATE_HAS_GCM_TAG = 9
        # All input has been read. After this, we switch back to STATE_IGNORING and wait for a new start byte.
        self.STATE_DONE = 10

        # Command line arguments
        self._args = {}

        # Serial connection from which we read the data from the smart meter
        self._connection = None

        # Initial empty values. These will be filled as content is read
        # and they will be reset each time we go back to the initial state.
        self._state = self.STATE_IGNORING
        self._buffer = ""
        self._buffer_length = 0
        self._next_state = 0
        self._system_title_length = 0
        self._system_title = b""
        self._data_length_bytes = b""  # length of "remaining data" in bytes
        self._data_length = 0  # length of "remaining data" as an integer
        self._frame_counter = b""
        self._payload = b""
        self._gcm_tag = b""
        
        # Use MQTT (True | False)
        self._useMQTT = False
        self._client = None
        self._mqtt_connected = False
        self._online = None
        self._last_telegram = time.time()
        self._gcm_ok = None
        self._security_byte = b"30"
        self._had_telegram = False
        self._discovery = os.getenv("DISCOVERY", "true").lower() not in ("false", "0", "no")
        self._discovery_prefix = os.getenv("DISCOVERY_PREFIX", "homeassistant") or "homeassistant"

        # DSMR-Parser nur einmal anlegen (Kopie der Spezifikation, das Original bleibt unverändert)
        self._telegram_parser = None
        if has_dsmr_parser:
            spec = dict(telegram_specifications.SAGEMCOM_T210_D_R)
            spec['general_global_cipher'] = False
            self._telegram_parser = TelegramParser(spec)

    def main(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('key', help="Decryption key")
        parser.add_argument('-i', '--serial-input-port', required=False, default="/dev/ttyUSB0", help="Input port. Defaults to /dev/ttyUSB0.")
        parser.add_argument('-o', '--serial-output-port', required=False, help="Output port, e.g. /dev/pts/2.")
        parser.add_argument('-a', '--aad', required=False, default="3000112233445566778899AABBCCDDEEFF", help="Additional authenticated data")
        parser.add_argument('-p', '--parse', action='store_true', required=False, default=False, help="Parse and pretty print DSMR v5 telegram")
        parser.add_argument('-m', '--mqtt-broker', required=False, help="MQTT broker ip/dns")
        parser.add_argument('-q', '--mqtt-port', required=False, default=1883, type=int, help="MQTT broker port")
        parser.add_argument('-u', '--mqtt-user', required=False, help="MQTT broker username")
        parser.add_argument('-v', '--mqtt-password', required=False, help="MQTT broker password")

        self._args = parser.parse_args()
        # Zugangsdaten/Schlüssel werden bewusst NICHT ausgegeben
        print(f"Austrian DSMR MQTT {APP_VERSION} – serieller Port: {self._args.serial_input_port}, "
              f"Broker: {self._args.mqtt_broker}, Discovery: {self._discovery}")

        self.connect()

        self._useMQTT = self._args.mqtt_broker is not None
        if self._useMQTT:
            if not has_dsmr_parser:
                print("DSMR-parser not found. MQTT disabled!")
                self._useMQTT = False
            else:
                self.mqtt_setup()

        while True:
            self.process()

    # ---------------- MQTT ----------------
    def mqtt_setup(self):
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "SmartMeter", reconnect_on_failure=True)
        if self._args.mqtt_user:
            self._client.username_pw_set(self._args.mqtt_user, self._args.mqtt_password)
        # Last Will: fällt die App weg, meldet der Broker "offline" -> HA zeigt "nicht verfügbar"
        self._client.will_set(STATUS_TOPIC, "offline", qos=1, retain=True)
        self._client.reconnect_delay_set(min_delay=1, max_delay=60)
        self._client.on_connect = self.on_connect
        self._client.on_disconnect = self.on_disconnect
        print("Connect MQTT...")
        try:
            self._client.connect(self._args.mqtt_broker, self._args.mqtt_port, keepalive=60)
        except Exception as e:
            # Broker (noch) nicht erreichbar: die Netzwerkschleife verbindet automatisch neu
            print(f"MQTT connect failed ({e}) – retrying in background")
            self._client.connect_async(self._args.mqtt_broker, self._args.mqtt_port, keepalive=60)
        self._client.loop_start()

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"MQTT connection refused: {reason_code}")
            return
        print("MQTT Connection successful")
        self._mqtt_connected = True
        self._online = None
        if self._discovery:
            self.publish_discovery()
        # Status wird beim nächsten gültigen Telegramm auf "online" gesetzt
        if self._had_telegram and time.time() - self._last_telegram < NO_DATA_TIMEOUT_S:
            self.set_online(True)

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        self._mqtt_connected = False
        print(f"MQTT disconnected ({reason_code}) – reconnecting automatically")

    def set_online(self, online):
        if not self._useMQTT or not self._mqtt_connected or self._online == online:
            return
        self._client.publish(STATUS_TOPIC, "online" if online else "offline", qos=1, retain=True)
        self._online = online
        print("Status:", "online" if online else "offline")

    def publish_discovery(self):
        for d in DISCOVERY_SENSORS:
            cfg = {
                "name": d["name"],
                "unique_id": d["unique_id"],
                "default_entity_id": d["default_entity_id"],
                "state_topic": f"{TOPIC_PREFIX}/{d['key']}",
                "icon": d["icon"],
                "availability_topic": STATUS_TOPIC,
                "payload_available": "online",
                "payload_not_available": "offline",
                "device": DEVICE,
                "origin": ORIGIN,
            }
            for k_cfg, k_def in (("unit_of_measurement", "unit"), ("device_class", "device_class"),
                                 ("state_class", "state_class"), ("entity_category", "entity_category")):
                if d.get(k_def):
                    cfg[k_cfg] = d[k_def]
            topic = f"{self._discovery_prefix}/sensor/austrian_dsmr_mqtt/{d['unique_id']}/config"
            self._client.publish(topic, json.dumps(cfg), qos=1, retain=True)
        print(f"Discovery published for {len(DISCOVERY_SENSORS)} sensors")

    def publish_value(self, name, payload):
        if not self._mqtt_connected:
            return False
        info = self._client.publish(f"{TOPIC_PREFIX}/{name}", payload, qos=0)
        return info.rc == mqtt.MQTT_ERR_SUCCESS

    # Connect to the serial port when we run the script
    def connect(self):
        """Serielle Schnittstelle öffnen; bei Fehler alle 5 s erneut versuchen."""
        while True:
            try:
                self._connection = serial.Serial(
                    port=self._args.serial_input_port,
                    baudrate=115200,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=5,
                )
                print("Serial connection established on", self._args.serial_input_port)
                self._state = self.STATE_IGNORING
                return
            except (serial.SerialException, OSError) as err:
                print(f"ERROR: Could not open serial port {self._args.serial_input_port}: {err} – retry in 5 s")
                self._connection = None
                time.sleep(5)

    def reconnect_serial(self, reason):
        print(f"Serial problem ({reason}) – reopening port")
        self.set_online(False)
        try:
            if self._connection is not None:
                self._connection.close()
        except Exception:
            pass
        self._connection = None
        time.sleep(5)
        self.connect()
        self._last_telegram = time.time()   # neue Frist ab Wiederverbindung

    # Start processing incoming data
    def process(self):
        try:
            raw_data = self._connection.read()
        except (serial.SerialException, OSError, AttributeError) as err:
            self.reconnect_serial(err)
            return

        if time.time() - self._last_telegram > NO_DATA_TIMEOUT_S:
            self.reconnect_serial(f"no valid telegram for {NO_DATA_TIMEOUT_S} s")
            return
        if not raw_data:          # Lese-Timeout (5 s) ohne Daten
            return

        # Read and parse the stream from the serial port byte by byte.
        # This parsing works as a state machine (see the definitions in the __init__ method).
        # See also the official documentation on http://smarty.creos.net/wp-content/uploads/P1PortSpecification.pdf
        # For better human readability, we use the hexadecimal representation of the input.
        hex_input = binascii.hexlify(raw_data)

        # Initial state. Input is ignored until start byte is detected.
        if self._state == self.STATE_IGNORING:
            if hex_input == b'db':
                self._state = self.STATE_STARTED
                self._buffer = b""
                self._buffer_length = 1
                self._system_title_length = 0
                self._system_title = b""
                self._data_length = 0
                self._data_length_bytes = b""
                self._frame_counter = b""
                self._payload = b""
                self._gcm_tag = b""
                self._security_byte = b"30"
            else:
                return

        # Start byte (hex "DB") has been detected.
        elif self._state == self.STATE_STARTED:
            self._state = self.STATE_HAS_SYSTEM_TITLE_LENGTH
            self._system_title_length = int(hex_input, 16)
            self._buffer_length = self._buffer_length + 1
            self._next_state = 2 + self._system_title_length  # start bytes + system title length

        # Length of system title has been read.
        elif self._state == self.STATE_HAS_SYSTEM_TITLE_LENGTH:
            if self._buffer_length > self._next_state:
                self._system_title += hex_input
                self._state = self.STATE_HAS_SYSTEM_TITLE
                self._next_state = self._next_state + 2  # read two more bytes
            else:
                self._system_title += hex_input

        # System title has been read.
        elif self._state == self.STATE_HAS_SYSTEM_TITLE:
            if hex_input == b'82':
                self._next_state = self._next_state + 1
                self._state = self.STATE_HAS_SYSTEM_TITLE_SUFFIX  # Ignore separator byte
            else:
                print("ERROR, expected 0x82 separator byte not found, dropping frame")
                self._state = self.STATE_IGNORING
 

        # Additional byte after the system title has been read.
        elif self._state == self.STATE_HAS_SYSTEM_TITLE_SUFFIX:
            if self._buffer_length > self._next_state:
                self._data_length_bytes += hex_input
                self._data_length = int(self._data_length_bytes, 16)
                self._state = self.STATE_HAS_DATA_LENGTH
            else:
                self._data_length_bytes += hex_input

        # Length of remaining data has been read.
        elif self._state == self.STATE_HAS_DATA_LENGTH:
            # Dieses Byte ist das Security-Control-Byte (0x30 = verschlüsselt + authentifiziert)
            self._security_byte = hex_input
            self._state = self.STATE_HAS_SEPARATOR
            self._next_state = self._next_state + 1 + 4  # separator byte + 4 bytes for framecounter

        # Additional byte after the remaining data length has been read.
        elif self._state == self.STATE_HAS_SEPARATOR:
            if self._buffer_length > self._next_state:
                self._frame_counter += hex_input
                #print("Framecounter")
                #print(self._frame_counter)
                self._state = self.STATE_HAS_FRAME_COUNTER
                self._next_state = self._next_state + self._data_length - 17
            else:
                self._frame_counter += hex_input

        # Frame counter has been read.
        elif self._state == self.STATE_HAS_FRAME_COUNTER:
            if self._buffer_length > self._next_state:
                self._payload += hex_input
                self._state = self.STATE_HAS_PAYLOAD
                self._next_state = self._next_state + 12
            else:
                self._payload += hex_input

        # Payload has been read.
        elif self._state == self.STATE_HAS_PAYLOAD:
            # All input has been read. After this, we switch back to STATE_IGNORING and wait for a new start byte.
            if self._buffer_length > self._next_state:
                self._gcm_tag += hex_input
                self._state = self.STATE_DONE
            else:
                self._gcm_tag += hex_input

        self._buffer += hex_input
        self._buffer_length = self._buffer_length + 1

        if self._state == self.STATE_DONE:
            # print(self._buffer)
            self.analyze()
            self._state = self.STATE_IGNORING

    # Once we have a full encrypted "telegram", put everything together for decryption.
    def analyze(self):
        key = binascii.unhexlify(self._args.key)
        additional_data = binascii.unhexlify(self._args.aad)
        # Für die GCM-Prüfung gilt: AAD = Security-Control-Byte + GAK (16 Byte).
        # Der Netzbetreiber liefert nur den GAK; ist bereits "30…" (17 Byte) eingetragen, bleibt es so.
        if len(additional_data) == 16:
            additional_data = binascii.unhexlify(self._security_byte) + additional_data
        iv = binascii.unhexlify(self._system_title + self._frame_counter)
        payload = binascii.unhexlify(self._payload)
        gcm_tag = binascii.unhexlify(self._gcm_tag)

        try:
            decryption = self.decrypt(key, additional_data, iv, payload, gcm_tag)
        except Exception as e:
            print(f"ERROR on decryption: {e}")
            return

        if not has_dsmr_parser:
            print(decryption)
        else:
            try:
                telegram = self._telegram_parser.parse(decryption.decode())
            except Exception as e:
                print(f"ERROR: Cannot parse DSMR Telegram: {e}")
                return

            self._last_telegram = time.time()
            self._had_telegram = True
            self.set_online(True)
            pub = 0
            for obisName, dsmr_object in telegram:
                try:
                    myvalue = int(dsmr_object.value)
                    myvalue_is_int = True
                except (TypeError, ValueError, ArithmeticError):
                    myvalue = dsmr_object.value
                    myvalue_is_int = False
                if self._args.parse:
                    print("%s: %s [%s]" % (obisName, myvalue, dsmr_object.unit))
                if self._useMQTT:
                    if myvalue_is_int:
                        ok = self.publish_value(obisName, myvalue)
                    elif obisName == "P1_MESSAGE_TIMESTAMP":
                        ok = self.publish_value(obisName, myvalue.isoformat().encode('utf-8'))
                    else:
                        ok = self.publish_value(obisName, str(myvalue).encode('utf-8'))
                    pub += 1 if ok else 0
            if pub > 0:
                try:
                    with open("/tmp/mqtt_last_send", "w") as f:
                        f.write(str(time.time()))
                except OSError:
                    pass

        if self._args.serial_output_port:
            self.write_to_serial_port(decryption)

    # Do the actual decryption (AES-GCM)
    def decrypt(self, key, additional_data, iv, payload, gcm_tag):
    #        decryptor = Cipher(
    #            algorithms.AES(key),
    #            modes.GCM(iv, gcm_tag, 12),
    #            backend=default_backend()
    #        ).decryptor()
    #
    #        decryptor.authenticate_additional_data(additional_data)##
    #
    #        return decryptor.update(payload) + decryptor.finalize()
        cipher = AES.new(key, AES.MODE_GCM, iv, mac_len=12)
        cipher.update(additional_data)
        try:
            # Prüft zusätzlich den GCM-Tag (Echtheit/Unversehrtheit des Telegramms)
            result = cipher.decrypt_and_verify(payload, gcm_tag)
            if self._gcm_ok is not True:
                print("GCM tag check OK")
                self._gcm_ok = True
            return result
        except ValueError:
            if self._gcm_ok is True:
                # Die Prüfung hat mit diesen Schlüsseln schon funktioniert -> Telegramm ist
                # beschädigt oder nicht echt: verwerfen.
                self._gcm_fail_count = getattr(self, "_gcm_fail_count", 0) + 1
                print(f"WARNING: GCM tag check failed – telegram dropped ({self._gcm_fail_count} so far)")
                raise ValueError("GCM tag mismatch")
            # Noch nie erfolgreich geprüft (z. B. falscher GAK): entschlüsseln wie bisher;
            # die CRC-Prüfung des DSMR-Parsers verwirft beschädigte Telegramme trotzdem.
            if self._gcm_ok is None:
                print("WARNING: GCM tag check failed – continuing without it (check GAK; CRC check stays active)")
            self._gcm_ok = False
            cipher = AES.new(key, AES.MODE_GCM, iv, mac_len=12)
            cipher.update(additional_data)
            return cipher.decrypt(payload)

    # Write the decrypted data to a serial port (e.g. one created with socat)
    def write_to_serial_port(self, decryption):
        ser = serial.Serial(
            port=self._args.serial_output_port,
            baudrate=115200,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )
        ser.write(decryption)
        ser.close()


if __name__ == '__main__':
    smarty_proxy = SmartyProxy()
    smarty_proxy.main()
