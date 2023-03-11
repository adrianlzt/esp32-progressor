import sys

sys.path.append("")

import time
import random
import struct
import aioble
import bluetooth
import json
import uasyncio as asyncio
from machine import Pin
from hx711_gpio import HX711

# Keys fot the config
OFFSET = 'offset'
SCALE = 'scale'

# Where is the HX711 connected
LOADCELL_DOUT_PIN = 2
LOADCELL_SCK_PIN = 0

# Progressor service and characteristics.
PROGRESSOR_UUID                     = bluetooth.UUID("7e4e1701-1ea6-40c9-9dcc-13d34ffead57")
DATA_CHARACTERISTIC_UUID            = bluetooth.UUID("7e4e1702-1ea6-40c9-9dcc-13d34ffead57")
CONTROL_POINT_CHARACTERISTIC_UUID   = bluetooth.UUID("7e4e1703-1ea6-40c9-9dcc-13d34ffead57")

# Progressor commands, received from the app.
CMD_TARE_SCALE = 100 # 0x64 'd'
CMD_START_WEIGHT_MEAS = 101 # 0x65 'e'
CMD_STOP_WEIGHT_MEAS = 102 # 0x66 'f'
CMD_START_PEAK_RFD_MEAS = 103 # 0x67 'g'
CMD_START_PEAK_RFD_MEAS_SERIES = 104 # 0x68 'h'
CMD_ADD_CALIBRATION_POINT = 105 # 0x69 'i'
CMD_SAVE_CALIBRATION = 106 #0x6a 'j'
CMD_GET_APP_VERSION = 107 # 0x6b 'k'
CMD_GET_ERROR_INFORMATION = 108 # 0x6c 'l'
CMD_CLR_ERROR_INFORMATION = 109 # 0x6d 'm'
CMD_ENTER_SLEEP = 110 # 0x6e 'n'

RES_CMD_RESPONSE = b'\x00'
RES_CMD_RESPONSE_ERROR = b'\x05'
RES_WEIGHT_MEAS = 1
RES_RFD_PEAK = 2
RES_RFD_PEAK_SERIES = 3
RES_LOW_PWR_WARNING = 4

# How frequently to send advertising beacons.
_ADV_INTERVAL_MS = 250_000


# Register GATT server.
progressor_service = aioble.Service(PROGRESSOR_UUID)

control_characteristic = aioble.Characteristic(
    progressor_service, CONTROL_POINT_CHARACTERISTIC_UUID, write=True, read=True
)
data_characteristic = aioble.Characteristic(
    progressor_service, DATA_CHARACTERISTIC_UUID, notify=True
)

aioble.register_services(progressor_service)

# Control if data is being sent to the app.
send_data = False

# Store timestamp from the start of measurements
start_meas = 0


def save_config():
    """Save the config file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

# Read config from file
CONFIG_FILE = 'config.json'
# If the config file exists, read it.
try:
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
except OSError:
    # If the file doesn't exist, create it with some defaults.
    config = {
        OFFSET: -42130,
        SCALE: 0.2123,
    }
    save_config()


# Initialize the HX711.
pin_OUT = Pin(LOADCELL_DOUT_PIN, Pin.IN, pull=Pin.PULL_DOWN)
pin_SCK = Pin(LOADCELL_SCK_PIN, Pin.OUT)
hx711 = HX711(pin_SCK, pin_OUT)
hx711.set_offset(config[OFFSET])
hx711.set_scale(config[SCALE])


def get_weight():
    """Read the weight sensor

    Do not return negative values
    """
    return (hx711.read() - hx711.OFFSET) * hx711.SCALE

def _encode_weight_values(weights):
    """Encode a list of weight measurements.

    Weight should be in Kg.
    Timestamp in microseconds.

    tag (1 byte), length (1 byte), Weight (float32), Timestamp (uint32_t)

    Length is the number of bytes of the payload.

    The payload could be several values (Weight, Timestamp) pairs.
    [CMD, LEN, W1, T1, W2, T2, ...]
    """
    length = len(weights) * 8
    header = struct.pack('<BB', RES_WEIGHT_MEAS, length)
    data = b""
    for weight_kg, timestamp_us in weights:
        data += struct.pack('<fI', weight_kg, timestamp_us)

    return header + data


# This would be periodically polling a hardware sensor.
async def sensor_task(connection):
    print("Starting sensor task")

    while True:
        if send_data:
            # Get 15 weight measurements, one each 10ms
            weights = []
            for _ in range(15):
                # TODO el contador hace un loop, por lo que si estamos mucho tiempo recogiendo datos podría
                # empezar a enviar los datos mal.
                # Calcular cuanto es ese tiempo por si debemos controlarlo.
                # https://docs.micropython.org/en/latest/library/time.html#time.ticks_ms
                weights.append((get_weight(), time.ticks_diff(time.ticks_us(), start_meas)))

            # Give time to pass the control to other tasks.
            await asyncio.sleep_ms(1)

            try:
                data_characteristic.notify(connection, _encode_weight_values(weights))
            except Exception as e:
                print("Error sending data, stop sending data", e)
                break

        else:
            await asyncio.sleep_ms(500)

async def control_task(connection):
    global send_data, start_meas

    # List of calibration points, used to calibrate the scale.
    calibration_points = []

    try:
        with connection.timeout(None):
            while True:
                print("Waiting for control message")
                await control_characteristic.written()
                msg = control_characteristic.read()

                cmd = struct.unpack('<B', msg)[0]

                if cmd == CMD_START_WEIGHT_MEAS:
                    print("CMD_START_WEIGHT_MEAS")
                    start_meas = time.ticks_us()
                    send_data = True

                elif cmd == CMD_STOP_WEIGHT_MEAS:
                    print("CMD_STOP_WEIGHT_MEAS")
                    send_data = False

                elif cmd == CMD_TARE_SCALE:
                    # This command is not used by the phone app.
                    print("CMD_TARE_SCALE")
                    hx711.tare()

                elif cmd == CMD_START_PEAK_RFD_MEAS:
                    print("CMD_START_PEAK_RFD_MEAS TODO")

                elif cmd == CMD_START_PEAK_RFD_MEAS_SERIES:
                    print("CMD_START_PEAK_RFD_MEAS_SERIES TODO")

                elif cmd == CMD_ADD_CALIBRATION_POINT:
                    # This command is used to calibrate the scale.
                    # The app sends the weight being used.
                    # We store this value and the current raw measure.
                    weight_kg = struct.unpack('<f', msg[1:5])[0]
                    calibration_points.append((weight_kg, hx711.read()))
                    print(f"CMD_ADD_CALIBRATION_POINT: {calibration_points}")

                elif cmd == CMD_SAVE_CALIBRATION:
                    # This command uses the last two calibration_points to calculate the scale and offset.
                    if len(calibration_points) < 2:
                        print("Not enough calibration points")
                        control_characteristic.write(RES_CMD_RESPONSE_ERROR)
                        continue

                    weight1, raw1 = calibration_points[-2]
                    weight2, raw2 = calibration_points[-1]

                    # Solve equation: weight = (raw - offset) * scale
                    scale = (weight2 - weight1) / (raw2 - raw1)
                    offset = raw1 - weight1 / scale
                    config[SCALE] = scale
                    config[OFFSET] = offset
                    save_config()

                    hx711.set_scale(scale)
                    hx711.set_offset(offset)

                    print(f"CMD_SAVE_CALIBRATION: {config}")

                elif cmd == CMD_GET_ERROR_INFORMATION:
                    print("CMD_GET_ERROR_INFORMATION TODO")

                elif cmd == CMD_CLR_ERROR_INFORMATION:
                    print("CMD_CLR_ERROR_INFORMATION TODO")

                elif cmd == CMD_ENTER_SLEEP:
                    print("CMD_ENTER_SLEEP")
                    send_data = False

                elif cmd == CMD_GET_APP_VERSION:
                    print("CMD_GET_APP_VERSION")
                    control_characteristic.notify(connection, b"1")

                else:
                    print(f"Unknown command: {cmd}")

                control_characteristic.write(RES_CMD_RESPONSE)

    except aioble.DeviceDisconnectedError:
        return

# Serially wait for connections. Don't advertise while a central is
# connected.
async def peripheral_task():
    global send_data

    while True:
        print("Waiting for connection")

        async with await aioble.advertise(
            _ADV_INTERVAL_MS,
            name="Progressor_1234",
            services=[PROGRESSOR_UUID],
        ) as connection:
            print("Connection from", connection.device)

            t = asyncio.create_task(sensor_task(connection))
            await control_task(connection)
            t.cancel()

            await connection.disconnected()
            print("Disconnection from", connection.device)
            send_data = False


# Run both tasks.
async def main():
    await peripheral_task()


asyncio.run(main())
