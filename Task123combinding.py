
import network, time, ujson
from umqtt.simple import MQTTClient
from machine import Pin, ADC, I2C
from mlx90614 import MLX90614

# =========================
# WiFi & MQTT Configuration
# =========================
SSID = "Robotic WIFI"
PASSWORD = "rbtWIFI@2025"

BROKER = "test.mosquitto.org"
PORT = 1883
CLIENT_ID = b"esp32_sensors_1"
TOPIC = b"/aupp/esp32/sensors"
KEEPALIVE = 30

# =========================
# MQ-5 Gas Sensor
# =========================
mq5 = ADC(Pin(34))
mq5.atten(ADC.ATTN_11DB)
mq5.width(ADC.WIDTH_12BIT)

readings = []
WINDOW_SIZE = 5

# =========================
# MLX90614 Temperature Sensor
# =========================
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=100000)
temp_sensor = MLX90614(i2c)


# =========================
# Gas Risk Classification
# =========================
def classify_gas(value):
    if value < 2100:
        return "SAFE"
    elif value < 2600:
        return "WARNING"
    else:
        return "DANGER"


# =========================
# WiFi Connection
# =========================
def wifi_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(SSID, PASSWORD)

        t0 = time.ticks_ms()

        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), t0) > 20000:
                raise RuntimeError("WiFi connection timeout")
            time.sleep(0.3)

    print("WiFi OK:", wlan.ifconfig())
    return wlan


# =========================
# MQTT Connection
# =========================
def make_client():
    return MQTTClient(
        client_id=CLIENT_ID,
        server=BROKER,
        port=PORT,
        keepalive=KEEPALIVE
    )


# =========================
# Main Program
# =========================
def main():

    wifi_connect()
    client = make_client()

    while True:
        try:
            client.connect()
            print("MQTT connected")

            while True:

                # ----- Task 1 & 2: Gas Filtering -----
                raw_value = mq5.read()

                readings.append(raw_value)
                if len(readings) > WINDOW_SIZE:
                    readings.pop(0)

                average_value = sum(readings) / len(readings)

                # Gas Risk Classification
                risk_level = classify_gas(average_value)

                # ----- Task 3: Fever Detection -----
                body_temp = temp_sensor.read_object_temp()

                fever_flag = 1 if body_temp >= 32.5 else 0

                # ----- Combine All Sensor Data -----
                data = {
                    "raw_value": raw_value,
                    "moving_average": round(average_value, 2),
                    "risk_level": risk_level,
                    "body_temperature": round(body_temp, 2),
                    "fever_flag": fever_flag
                }

                # ----- MQTT Publish -----
                msg = ujson.dumps(data).encode()
                client.publish(TOPIC, msg)

                # ----- Display Results -----
                print("Gas Raw Value:", raw_value)
                print("Gas Average:", round(average_value, 2))
                print("Gas Risk:", risk_level)
                print("Body Temperature:", round(body_temp, 2), "C")
                print("Fever Flag:", fever_flag)
                print("MQTT Sent:", msg)
                print("-------------------------")

                time.sleep(2)

        except OSError as e:
            print("Connection error:", e)

            try:
                client.close()
            except:
                pass

            print("Reconnecting in 3 seconds...")
            time.sleep(3)
            wifi_connect()


main()
