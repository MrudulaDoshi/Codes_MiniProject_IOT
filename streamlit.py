import json
from pathlib import Path

import pandas as pd
import streamlit as st
import paho.mqtt.publish as mqtt_publish

from streamlit_autorefresh import st_autorefresh


# ==================================================
# 1. PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="Smart Agriculture IoT Dashboard",
    page_icon="🌱",
    layout="wide"
)


# ==================================================
# 2. PROJECT CONFIGURATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_FILE = BASE_DIR / "sensor_data.json"
HISTORY_FILE = BASE_DIR / "sensor_history.csv"

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883

SENSOR_TOPIC = "smartagri/demo/esp32_84127/sensors"
CONTROL_TOPIC = "smartagri/demo/esp32_84127/control"

DEFAULT_THRESHOLD = 30
MIN_THRESHOLD = 10
MAX_THRESHOLD = 80
THRESHOLD_STEP = 5

REFRESH_INTERVAL = 3000

EXPECTED_COLUMNS = [
    "timestamp",
    "soil_moisture",
    "temperature",
    "humidity",
    "irrigation",
    "threshold"
]


# ==================================================
# 3. AUTOMATIC REFRESH
# ==================================================

st_autorefresh(
    interval=REFRESH_INTERVAL,
    limit=None,
    key="smart_agriculture_refresh"
)


# ==================================================
# 4. HELPER FUNCTIONS
# ==================================================

def read_latest_data():

    if not DATA_FILE.exists():
        return None

    try:

        with open(
            DATA_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if isinstance(data, dict):
            return data

        return None

    except (json.JSONDecodeError, OSError):
        return None


def read_history():

    if not HISTORY_FILE.exists():
        return pd.DataFrame(columns=EXPECTED_COLUMNS)

    try:

        df = pd.read_csv(HISTORY_FILE)

        if df.empty:
            return pd.DataFrame(columns=EXPECTED_COLUMNS)

        # Ensure that all expected columns exist.
        for column in EXPECTED_COLUMNS:

            if column not in df.columns:
                df[column] = None

        df = df[EXPECTED_COLUMNS].copy()

        # Convert timestamps.
        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce",
            utc=True
        )

        # Convert readings into numeric values.
        numeric_columns = [
            "soil_moisture",
            "temperature",
            "humidity",
            "threshold"
        ]

        for column in numeric_columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

        # Keep only rows with valid timestamps.
        df = df.dropna(subset=["timestamp"])

        df = df.sort_values("timestamp")

        return df.reset_index(drop=True)

    except (OSError, pd.errors.ParserError, ValueError):
        return pd.DataFrame(columns=EXPECTED_COLUMNS)


def get_numeric_value(data, key, default=None):

    try:

        value = data.get(key, default)

        if value is None:
            return None

        value = float(value)

        if pd.isna(value):
            return None

        return value

    except (TypeError, ValueError):
        return None


def prepare_chart_data(history, latest):

    history = history.copy()

    if latest is None:
        return history

    try:

        soil = get_numeric_value(
            latest,
            "soil_moisture"
        )

        temperature = get_numeric_value(
            latest,
            "temperature"
        )

        humidity = get_numeric_value(
            latest,
            "humidity"
        )

        threshold = get_numeric_value(
            latest,
            "threshold",
            DEFAULT_THRESHOLD
        )

        if soil is None:
            return history

        timestamp_value = latest.get("timestamp")

        timestamp = pd.to_datetime(
            timestamp_value,
            errors="coerce",
            utc=True
        )

        if pd.isna(timestamp):
            timestamp = pd.Timestamp.now(tz="UTC")

        new_row = {
            "timestamp": timestamp,
            "soil_moisture": soil,
            "temperature": temperature,
            "humidity": humidity,
            "irrigation": latest.get(
                "irrigation",
                "UNKNOWN"
            ),
            "threshold": (
                threshold
                if threshold is not None
                else DEFAULT_THRESHOLD
            )
        }

        # Add latest data only if its timestamp is not
        # already present in the CSV history.
        if history.empty:

            history = pd.DataFrame(
                [new_row],
                columns=EXPECTED_COLUMNS
            )

        else:

            latest_time = history["timestamp"].max()

            if pd.isna(latest_time) or timestamp > latest_time:

                history = pd.concat(
                    [
                        history,
                        pd.DataFrame([new_row])
                    ],
                    ignore_index=True
                )

        history = history.sort_values("timestamp")

        # Display the latest 500 readings.
        return history.tail(500).reset_index(drop=True)

    except (TypeError, ValueError, KeyError):
        return history


def send_threshold(threshold):

    mqtt_publish.single(
        topic=CONTROL_TOPIC,
        payload=str(int(threshold)),
        hostname=MQTT_BROKER,
        port=MQTT_PORT,
        qos=0,
        retain=False,
        keepalive=30,
        client_id="SmartAgriDashboardControl_84127"
    )


def format_timestamp(value):

    if pd.isna(value):
        return "Unknown"

    return value.strftime("%Y-%m-%d %H:%M:%S UTC")


# ==================================================
# 5. DASHBOARD HEADER
# ==================================================

st.title("🌱 Smart Agriculture IoT Dashboard")

st.markdown(
    """
    **Real-Time Soil Monitoring and Automatic Irrigation**

    Monitor simulated soil moisture, air temperature and humidity.
    Observe automatic irrigation decisions and adjust the moisture
    threshold through MQTT.
    """
)

st.caption(
    "Simulation: Wokwi ESP32 | Communication: MQTT | "
    "Dashboard: Python + Streamlit"
)

st.divider()


# ==================================================
# 6. SIDEBAR: IRRIGATION CONTROL
# ==================================================

st.sidebar.header("⚙️ Irrigation Settings")

st.sidebar.write(
    "Choose the minimum soil moisture level that "
    "should trigger irrigation."
)

if "selected_threshold" not in st.session_state:

    st.session_state.selected_threshold = DEFAULT_THRESHOLD

with st.sidebar.form("threshold_form"):

    selected_threshold = st.slider(
        "Soil Moisture Threshold (%)",
        min_value=MIN_THRESHOLD,
        max_value=MAX_THRESHOLD,
        value=int(st.session_state.selected_threshold),
        step=THRESHOLD_STEP
    )

    apply_button = st.form_submit_button(
        "Apply Threshold",
        use_container_width=True
    )

if apply_button:

    try:

        send_threshold(selected_threshold)

        st.session_state.selected_threshold = selected_threshold

        st.sidebar.success(
            f"Threshold command sent: {selected_threshold}%"
        )

        st.sidebar.info(
            "The ESP32 must be running and connected to MQTT. "
            "Check its Serial Monitor for THRESHOLD UPDATED."
        )

    except Exception as error:

        st.sidebar.error(
            "Could not send the MQTT command. "
            "Check your internet connection and MQTT broker."
        )

        st.sidebar.caption(str(error))


st.sidebar.divider()

st.sidebar.markdown(
    """
    **Control logic**

    - Moisture below threshold: irrigation ON.
    - Moisture at or above threshold: irrigation OFF.
    - Control messages are sent through MQTT.
    """
)


# ==================================================
# 7. LOAD SENSOR DATA
# ==================================================

latest_data = read_latest_data()

history = read_history()

chart_data = prepare_chart_data(
    history,
    latest_data
)


# ==================================================
# 8. DATA AVAILABILITY
# ==================================================

if latest_data is None:

    st.warning(
        "No sensor data is available yet."
    )

    st.markdown(
        """
        Start the system in this order:

        1. Start the Wokwi ESP32 simulation.
        2. Run `mqtt_subscriber.py` in a VS Code terminal.
        3. Keep the subscriber running.
        4. Run `streamlit_app.py` in another terminal.
        """
    )

    st.stop()


# ==================================================
# 9. CURRENT SENSOR READINGS
# ==================================================

st.subheader("📡 Current Sensor Readings")

soil_moisture = get_numeric_value(
    latest_data,
    "soil_moisture"
)

temperature = get_numeric_value(
    latest_data,
    "temperature"
)

humidity = get_numeric_value(
    latest_data,
    "humidity"
)

threshold = get_numeric_value(
    latest_data,
    "threshold",
    DEFAULT_THRESHOLD
)

irrigation = str(
    latest_data.get("irrigation", "UNKNOWN")
).upper()

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "🌱 Soil Moisture",
        f"{soil_moisture:.1f}%" if soil_moisture is not None else "N/A"
    )

with col2:

    st.metric(
        "🌡️ Temperature",
        f"{temperature:.1f} °C" if temperature is not None else "N/A"
    )

with col3:

    st.metric(
        "💧 Air Humidity",
        f"{humidity:.1f}%" if humidity is not None else "N/A"
    )

with col4:

    st.metric(
        "🚿 Irrigation",
        irrigation
    )

st.caption(
    "Last sensor reading: "
    + format_timestamp(
        pd.to_datetime(
            latest_data.get("timestamp"),
            errors="coerce",
            utc=True
        )
    )
)

st.divider()


# ==================================================
# 10. IRRIGATION STATUS
# ==================================================

st.subheader("🚿 Automatic Irrigation Status")

status_col, moisture_col = st.columns(2)

with status_col:

    if irrigation == "ON":

        st.success(
            "🟢 Irrigation ON — LED should be illuminated."
        )

    elif irrigation == "OFF":

        st.info(
            "⚪ Irrigation OFF — LED should be switched off."
        )

    else:

        st.warning(
            "Irrigation status is unavailable."
        )

with moisture_col:

    if soil_moisture is not None:

        st.write(
            f"Current soil moisture: {soil_moisture:.1f}%"
        )

        st.progress(
            max(
                0.0,
                min(soil_moisture / 100.0, 1.0)
            )
        )

        if threshold is not None:

            st.write(
                f"ESP32 threshold: {threshold:.0f}%"
            )

            if soil_moisture < threshold:

                st.warning(
                    "Moisture is below the threshold."
                )

            else:

                st.success(
                    "Moisture is at or above the threshold."
                )

st.divider()


# ==================================================
# 11. CHART DATA PREPARATION
# ==================================================

# Remove rows without usable timestamps.
plot_data = chart_data.dropna(
    subset=["timestamp"]
).copy()

# Remove timezone information for simpler chart indexing.
if not plot_data.empty:

    plot_data["timestamp"] = (
        plot_data["timestamp"].dt.tz_convert(None)
    )

# Sort readings from oldest to newest.
plot_data = plot_data.sort_values("timestamp")

# Use timestamps as the horizontal chart axis.
if not plot_data.empty:

    plot_data = plot_data.set_index("timestamp")


# ==================================================
# 12. SOIL MOISTURE LINE CHART
# ==================================================

st.subheader("📈 1. Soil Moisture vs Time")

st.caption(
    "The line shows the change in simulated soil moisture "
    "over successive readings. The dashed line represents "
    "the irrigation threshold."
)

if (
    not plot_data.empty
    and plot_data["soil_moisture"].notna().any()
):

    soil_chart = plot_data[
        ["soil_moisture"]
    ].dropna().copy()

    # Add a horizontal threshold series.
    soil_chart["Irrigation Threshold"] = (
        plot_data["threshold"].reindex(
            soil_chart.index
        ).fillna(DEFAULT_THRESHOLD)
    )

    st.line_chart(
        soil_chart,
        height=320,
        use_container_width=True
    )

    st.caption(
        f"Readings available: {len(soil_chart)}"
    )

else:

    st.info(
        "Soil moisture chart will appear when readings are received."
    )


# ==================================================
# 13. TEMPERATURE LINE CHART
# ==================================================

st.subheader("📈 2. Temperature vs Time")

st.caption(
    "Temperature readings from the simulated DHT22 sensor."
)

if (
    not plot_data.empty
    and plot_data["temperature"].notna().any()
):

    temperature_chart = plot_data[
        ["temperature"]
    ].dropna()

    st.line_chart(
        temperature_chart,
        height=300,
        use_container_width=True
    )

    st.caption(
        f"Readings available: {len(temperature_chart)}"
    )

else:

    st.info(
        "Temperature chart will appear when valid readings are received."
    )


# ==================================================
# 14. HUMIDITY LINE CHART
# ==================================================

st.subheader("📈 3. Air Humidity vs Time")

st.caption(
    "Relative humidity readings from the simulated DHT22 sensor."
)

if (
    not plot_data.empty
    and plot_data["humidity"].notna().any()
):

    humidity_chart = plot_data[
        ["humidity"]
    ].dropna()

    st.line_chart(
        humidity_chart,
        height=300,
        use_container_width=True
    )

    st.caption(
        f"Readings available: {len(humidity_chart)}"
    )

else:

    st.info(
        "Humidity chart will appear when valid readings are received."
    )


st.divider()


# ==================================================
# 15. RECENT SENSOR HISTORY
# ==================================================

st.subheader("📋 Recent Sensor History")

if not plot_data.empty:

    display_history = (
        plot_data.reset_index()
        .sort_values("timestamp", ascending=False)
        .head(20)
        .copy()
    )

    display_history["timestamp"] = (
        display_history["timestamp"]
        .dt.strftime("%Y-%m-%d %H:%M:%S")
    )

    st.dataframe(
        display_history,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "History will appear after sensor readings are received."
    )


st.divider()


# ==================================================
# 16. SENSOR STATISTICS
# ==================================================

st.subheader("📊 Sensor Statistics")

stat1, stat2, stat3 = st.columns(3)

with stat1:

    valid_soil = plot_data["soil_moisture"].dropna()

    if not valid_soil.empty:

        st.metric(
            "Average Soil Moisture",
            f"{valid_soil.mean():.1f}%"
        )

    else:

        st.metric("Average Soil Moisture", "N/A")

with stat2:

    valid_temperature = plot_data["temperature"].dropna()

    if not valid_temperature.empty:

        st.metric(
            "Average Temperature",
            f"{valid_temperature.mean():.1f} °C"
        )

    else:

        st.metric("Average Temperature", "N/A")

with stat3:

    valid_humidity = plot_data["humidity"].dropna()

    if not valid_humidity.empty:

        st.metric(
            "Average Air Humidity",
            f"{valid_humidity.mean():.1f}%"
        )

    else:

        st.metric("Average Air Humidity", "N/A")


# ==================================================
# 17. PROJECT TOOLS AND TECHNOLOGIES
# ==================================================

st.divider()

st.subheader("🛠️ Project Tools and Technologies")

tools_data = {
    "Component": [
        "Simulation Platform",
        "Embedded Controller",
        "Soil Moisture Input",
        "Temperature and Humidity Sensor",
        "Irrigation Output",
        "Communication Protocol",
        "MQTT Broker",
        "Programming Language",
        "Python MQTT Library",
        "Data Processing",
        "Dashboard Framework",
        "Data Storage",
        "Development Environment"
    ],

    "Technology Used": [
        "Wokwi",
        "ESP32",
        "Potentiometer (simulated soil moisture)",
        "DHT22",
        "LED (simulated irrigation output)",
        "MQTT over Wi-Fi",
        "HiveMQ Public MQTT Broker",
        "C++ and Python",
        "Paho-MQTT",
        "Pandas",
        "Streamlit",
        "JSON and CSV files",
        "Visual Studio Code"
    ]
}

st.dataframe(
    pd.DataFrame(tools_data),
    use_container_width=True,
    hide_index=True
)

st.caption(
    "The project is a software-based IoT simulation. "
    "No physical pump or real soil sensor is connected."
)


# ==================================================
# 18. FOOTER
# ==================================================

st.divider()

st.caption(
    "Smart Agriculture IoT System | "
    "Wokwi + ESP32 + MQTT + Python + Streamlit"
)

st.caption(
    "Automatic dashboard refresh: every 3 seconds."
)
