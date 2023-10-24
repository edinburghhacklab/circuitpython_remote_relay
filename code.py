import binascii
import board
import digitalio
import microcontroller
import os
import socketpool
import supervisor
import ssl
import time
import watchdog
import wifi

import adafruit_logging as logging
import adafruit_minimqtt.adafruit_minimqtt as MQTT

esp_uid = binascii.hexlify(microcontroller.cpu.uid).decode("ascii")

CIRCUITPY_WIFI_SSID = os.getenv("CIRCUITPY_WIFI_SSID")
CIRCUITPY_WIFI_PASSWORD = os.getenv("CIRCUITPY_WIFI_PASSWORD")
WIFI_HOSTNAME = os.getenv("WIFI_HOSTNAME", 'esp-{esp_uid}')
MQTT_HOST = os.getenv("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
if os.getenv("MQTT_TLS", "") in ["true", 1]:
    MQTT_TLS = True
else:
    MQTT_TLS = False
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_TOPIC = os.getenv("MQTT_TOPIC")
MQTT_DEBUG_TOPIC = os.getenv("MQTT_DEBUG_TOPIC", f"debug/esp-{esp_uid}")
WATCHDOG_TIMEOUT = int(os.getenv("WATCHDOG_TIMEOUT", 180))

supervisor.set_next_code_file(
    None,
    reload_on_success=True,
    reload_on_error=True,
)

wifi.radio.hostname = WIFI_HOSTNAME
pool = socketpool.SocketPool(wifi.radio)

relay = digitalio.DigitalInOut(board.D1)
relay.direction = digitalio.Direction.OUTPUT


def handle_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT {MQTT_HOST}:{MQTT_PORT}")
    client.subscribe(MQTT_TOPIC)
    client.publish(MQTT_DEBUG_TOPIC, f"connected, {supervisor.runtime.run_reason} {supervisor.get_previous_traceback()}")


def handle_disconnect(client, userdata, rc):
    print("Disconnected from MQTT")


def handle_message(client, topic, message):
    if message == "1":
        if not relay.value:
            relay.value = True
            client.publish(MQTT_DEBUG_TOPIC, "on")
            print("on")
    else:
        if relay.value:
            relay.value = False
            client.publish(MQTT_DEBUG_TOPIC, "off")
            print("off")


def main():
    print(f"Connecting to SSID {CIRCUITPY_WIFI_SSID}...")
    wifi.radio.connect(CIRCUITPY_WIFI_SSID, CIRCUITPY_WIFI_PASSWORD)
    print(f"Connected to SSID {CIRCUITPY_WIFI_SSID}, IP {wifi.radio.ipv4_address}")

    if MQTT_TLS:
        ssl_context = ssl.create_default_context()
    else:
        ssl_context = None

    mqtt_client = MQTT.MQTT(
        broker=MQTT_HOST,
        port=MQTT_PORT,
        username=MQTT_USERNAME,
        password=MQTT_PASSWORD,
        socket_pool=pool,
        is_ssl=MQTT_TLS,
        ssl_context=ssl_context,
        socket_timeout=0.1,
        client_id=esp_uid,
    )

    mqtt_client.enable_logger(logging)
    mqtt_client.on_connect = handle_connect
    mqtt_client.on_disconnect = handle_disconnect
    mqtt_client.on_message = handle_message
    mqtt_client.will_set(MQTT_DEBUG_TOPIC, "disconnected")
    mqtt_client.connect()

    while True:
        wdt.feed()
        mqtt_client.loop()

wdt = microcontroller.watchdog
wdt.timeout = WATCHDOG_TIMEOUT
wdt.mode = watchdog.WatchDogMode.RESET

main()
