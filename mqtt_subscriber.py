import json
import csv
import time
from pathlib import Path
from datetime import datetime

import paho.mqtt.client as mqtt


# ==================================================
# 1. PROJECT CONFIGURATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_FILE = BASE_DIR / "sensor_data.json"
HISTORY_FILE = BASE_DIR / "sensor_history.csv"

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883

MQTT_TOPIC = "smartagri/demo/esp32_84127/sensors"

DEFAULT_THRESHOLD = 30

CSV_COLUMNS = [
    "timestamp",
    "soil_moisture",
    "temperature",
    "humidity",
    "irrigation",
    "threshold"
]


# ==================================================
# 2. SAVE LATEST SENSOR READING
# ==================================================

def save_latest_data(data):

    temporary_file = DATA_FILE.with_suffix(".tmp")

    with open(
        temporary_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=4
        )

    temporary_file.replace(DATA_FILE)


# ==================================================
# 3. SAVE SENSOR HISTORY
# ==================================================

def save_history(data):

    file_exists = HISTORY_FILE.exists()

    write_header = (
        not file_exists
        or HISTORY_FILE.stat().st_size == 0
    )

    with open(
        HISTORY_FILE,
        "a",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=CSV_COLUMNS
        )

        if write_header:
            writer.writeheader()

        writer.writerow({
            "timestamp": data["timestamp"],
            "soil_moisture": data["soil_moisture"],
            "temperature": data["temperature"],
            "humidity": data["humidity"],
            "irrigation": data["irrigation"],
            "threshold": data["threshold"]
        })


# ==================================================
# 4. HANDLE CONNECTION
# ==================================================

def on_connect(client, userdata, flags, reason_code, properties):

    if reason_code.is_failure:

        print("MQTT connection failed:", reason_code)
        return

    print("Connected to MQTT broker successfully.")

    result, message_id = client.subscribe(
        MQTT_TOPIC,
        qos=0
    )

    if result == mqtt.MQTT_ERR_SUCCESS:

        print("Subscribed to sensor topic:")
        print(MQTT_TOPIC)

    else:

        print("Could not subscribe to the sensor topic.")


# ==================================================
# 5. HANDLE INCOMING SENSOR MESSAGES
# ==================================================

def on_message(client, userdata, message):

    try:

        payload = message.payload.decode("utf-8")

        sensor_data = json.loads(payload)

        if not isinstance(sensor_data, dict):
            print("Invalid sensor message: expected JSON object.")
            return

        if "soil_moisture" not in sensor_data:
            print("Sensor message has no soil moisture value.")
            return

        moisture = float(sensor_data["soil_moisture"])

        if not 0 <= moisture <= 100:
            print("Invalid soil moisture value.")
            return

        temperature = sensor_data.get("temperature")
        humidity = sensor_data.get("humidity")

        if temperature is not None:
            temperature = float(temperature)

        if humidity is not None:
            humidity = float(humidity)

        if temperature is not None and not -40 <= temperature <= 80:
            print("Invalid temperature value.")
            return

        if humidity is not None and not 0 <= humidity <= 100:
            print("Invalid humidity value.")
            return

        threshold = int(
            sensor_data.get(
                "threshold",
                DEFAULT_THRESHOLD
            )
        )

        irrigation = str(
            sensor_data.get(
                "irrigation",
                "UNKNOWN"
            )
        ).upper()

        if irrigation not in ("ON", "OFF"):
            irrigation = "UNKNOWN"

        # Use a timestamp for every received message.
        timestamp = datetime.now().astimezone().isoformat(
            timespec="seconds"
        )

        data = {
            "timestamp": timestamp,
            "soil_moisture": moisture,
            "temperature": temperature,
            "humidity": humidity,
            "irrigation": irrigation,
            "threshold": threshold
        }

        # Save the latest reading.
        save_latest_data(data)

        # Append this reading to historical CSV data.
        save_history(data)

        print()
        print("=" * 40)
        print("SMART AGRICULTURE")
        print("Time:", timestamp)
        print(f"Soil Moisture: {moisture:.1f}%")

        if temperature is not None:
            print(f"Temperature: {temperature:.1f} °C")
        else:
            print("Temperature: unavailable")

        if humidity is not None:
            print(f"Air Humidity: {humidity:.1f}%")
        else:
            print("Air Humidity: unavailable")

        print("Threshold:", threshold, "%")
        print("Irrigation Status:", irrigation)

        print("Latest reading saved to sensor_data.json")
        print("History appended to sensor_history.csv")
        print("=" * 40)

    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError) as error:

        print("Could not process sensor message:", error)

    except OSError as error:

        print("Could not save sensor data:", error)


# ==================================================
# 6. HANDLE DISCONNECTION
# ==================================================

def on_disconnect(
    client,
    userdata,
    disconnect_flags,
    reason_code,
    properties
):

    if reason_code.is_failure:
        print("MQTT disconnected unexpectedly:", reason_code)
    else:
        print("Disconnected from MQTT broker.")


# ==================================================
# 7. START MQTT SUBSCRIBER
# ==================================================

def main():

    print("=" * 45)
    print("SMART AGRICULTURE MQTT SUBSCRIBER")
    print("=" * 45)

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="SmartAgriSubscriber_84127"
    )

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    client.reconnect_delay_set(
        min_delay=1,
        max_delay=30
    )

    try:

        print("Connecting to MQTT broker...")

        client.connect(
            MQTT_BROKER,
            MQTT_PORT,
            keepalive=60
        )

        print("Waiting for sensor readings...")
        print("Press Ctrl+C to stop.")

        client.loop_forever()

    except KeyboardInterrupt:

        print("\nSubscriber stopped by user.")

    except (OSError, mqtt.MQTTException) as error:

        print("MQTT subscriber error:", error)

    finally:

        client.disconnect()


if __name__ == "__main__":
    main()
