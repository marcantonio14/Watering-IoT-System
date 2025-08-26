"""
Plant Monitoring and Automatic Watering System
----------------------------------------------
Board: Raspberry Pi Pico W (RP2040)
Sensors:
  - DHT22 (Temperature & Humidity) on GPIO 15
  - Soil Moisture Sensor (ADC1) with heater pin on GPIO 21
Actuators:
  - Pump controlled via L298N or similar motor driver
  - Motor pins: IN1=GPIO0, IN2=GPIO1, ENA=GPIO2 (PWM)

Features:
  - Connects to Wi-Fi
  - Syncs time via NTP
  - Reads temperature, humidity, and soil moisture
  - Uploads data to ThingSpeak every hour
  - Waters plants automatically at 08:00 and 20:00 if soil is dry
  - Sends status updates to ThingSpeak

Free to use and modify. 
Tested on Raspberry Pi Pico W (RP2040). 
No warranty provided.
"""

import network
import time
import ntptime
import machine
import dht
import requests


# ========================
# Configuration
# ========================

API_KEY = "xxxxxxxxxxxxxxxx"   # ThingSpeak API key
SSID = "YOUR_SSID"             # WiFi SSID
PASSWORD = "YOUR_PW"           # WiFi password

# Pin setup
DHT_SENSOR = dht.DHT22(machine.Pin(15))
HEAT_PIN_TEMP = machine.Pin(14, machine.Pin.OUT)

ADC_SOIL = machine.ADC(1)
HEAT_PIN_SOIL = machine.Pin(21, machine.Pin.OUT)

# Motor pins (pump control)
IN1 = machine.Pin(0, machine.Pin.OUT)
IN2 = machine.Pin(1, machine.Pin.OUT)
ENA = machine.PWM(machine.Pin(2))
ENA.freq(1000)  # 1kHz PWM frequency


# ========================
# WiFi & Time Functions
# ========================

def connect_to_wifi():
    """Connects ESP32/ESP8266 to Wi-Fi."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)

    while not wlan.isconnected():
        print("Connecting to Wi-Fi...")
        time.sleep(2)

    print("✅ Connected to Wi-Fi")
    print("📡 IP Address:", wlan.ifconfig()[0])


def get_current_time(timezone_offset=2):
    """Returns local time tuple with timezone offset applied."""
    t = time.localtime(time.time() + timezone_offset * 3600)
    return t


# ========================
# Sensor Functions
# ========================

def get_temperature(verbose=False):
    """Reads temperature and humidity from DHT22."""
    HEAT_PIN_TEMP.value(1)
    time.sleep(1)
    DHT_SENSOR.measure()
    temp = DHT_SENSOR.temperature()
    hum = DHT_SENSOR.humidity()
    if verbose:
        print(f"🌡️ Temp: {temp:.1f}°C   💧 Humidity: {hum:.1f}%")
    HEAT_PIN_TEMP.value(0)
    return temp, hum


def get_soil_humidity(verbose=False):
    """Reads soil moisture level from ADC (raw value)."""
    HEAT_PIN_SOIL.value(1)
    time.sleep(1)
    raw = ADC_SOIL.read_u16()
    if verbose:
        print(f"🌱 Soil Raw Value: {raw}")
    HEAT_PIN_SOIL.value(0)
    return raw


# ========================
# Motor Control
# ========================

def motor_forward(speed=65535):
    """Runs the motor forward at given speed (0–65535)."""
    IN1.value(1)
    IN2.value(0)
    ENA.duty_u16(speed)


def motor_stop():
    """Stops the motor."""
    ENA.duty_u16(0)
    IN1.value(0)
    IN2.value(0)


# ========================
# ThingSpeak Communication
# ========================

def upload_values():
    """Uploads sensor readings to ThingSpeak."""
    field1_value = get_soil_humidity()
    time.sleep(2)
    field2_value, field3_value = get_temperature()
    time.sleep(2)

    url = (f"https://api.thingspeak.com/update?api_key={API_KEY}"
           f"&field1={field1_value}&field2={field2_value}&field3={field3_value}")

    response = requests.get(url)
    print("📤 ThingSpeak Response:", response.text)


def channel_update(msg):
    """Sends a status update to ThingSpeak."""
    t = time.localtime()
    timestamp = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(*t[:6])
    status_message = f"[{timestamp}] - {msg}"

    url = "https://api.thingspeak.com/update"
    payload = {"api_key": API_KEY, "status": status_message}

    resp = requests.post(url, data=payload)
    print("📢 Status Response:", resp.text)
    resp.close()


# ========================
# Main Program
# ========================

def main():
    """Main loop for plant monitoring and watering system."""
    connect_to_wifi()

    # Sync time with NTP
    ntptime.host = "pool.ntp.org"
    ntptime.settime()

    now = get_current_time()
    hour = now[3]
    channel_update("System ON!")

    last_upload = time.time()   # Track last upload time
    plant_watered = False       # Watering flag

    while True:
        current_time = time.time()

        # Upload data every hour
        if current_time - last_upload >= 3600:
            upload_values()
            last_upload = current_time
            hour = (hour + 1) % 24

        # Water plants only at 8 AM or 8 PM
        if hour in (8, 20):
            if not plant_watered:
                soil_value = get_soil_humidity()
                if soil_value > 16000:  # Threshold for dry soil
                    print("🚿 Watering plants...")
                    motor_forward(32768)
                    time.sleep(60)
                    motor_stop()
                    channel_update("Plants watered!")
                    plant_watered = True
        else:
            plant_watered = False

        time.sleep(30)


if __name__ == "__main__":
    main()