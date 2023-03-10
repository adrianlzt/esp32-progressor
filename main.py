import sys

sys.path.append("")

import uasyncio as asyncio
import aioble
import bluetooth
import time

import random
import struct

# Progressor service and characteristics.
PROGRESSOR_UUID                     = bluetooth.UUID("7e4e1701-1ea6-40c9-9dcc-13d34ffead57")
DATA_CHARACTERISTIC_UUID            = bluetooth.UUID("7e4e1702-1ea6-40c9-9dcc-13d34ffead57")
CONTROL_POINT_CHARACTERISTIC_UUID   = bluetooth.UUID("7e4e1703-1ea6-40c9-9dcc-13d34ffead57")

# Comandos para el progressor
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

RES_CMD_RESPONSE = 0
RES_WEIGHT_MEAS = 1
RES_RFD_PEAK = 2
RES_RFD_PEAK_SERIES = 3
RES_LOW_PWR_WARNING = 4

# How frequently to send advertising beacons.
_ADV_INTERVAL_MS = 250_000


# Register GATT server.
progressor_service = aioble.Service(PROGRESSOR_UUID)

control_characteristic = aioble.Characteristic(
    progressor_service, CONTROL_POINT_CHARACTERISTIC_UUID, write=True
)
data_characteristic = aioble.Characteristic(
    progressor_service, DATA_CHARACTERISTIC_UUID, notify=True
)

aioble.register_services(progressor_service)

# Controla la task de envio de datos
send_data = False

# Timestamp de inicio de la medición
start_meas = 0


weight = 24.5
def get_weight():
    """Simulate a weight sensor."""
    global weight
    weight += random.uniform(-0.5, 0.5)
    return weight


# Helper to encode the temperature characteristic encoding (sint16, hundredths of a degree).
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
                await asyncio.sleep_ms(10)

            data_characteristic.notify(connection, _encode_weight_values(weights))

        else:
            await asyncio.sleep_ms(500)

async def control_task(connection):
    global send_data, start_meas

    try:
        with connection.timeout(None):
            while True:
                print("Waiting for control message")
                await control_characteristic.written()
                msg = control_characteristic.read()
                control_characteristic.write(b"")

                if ord(msg) == CMD_START_WEIGHT_MEAS:
                    print("CMD_START_WEIGHT_MEAS")
                    start_meas = time.ticks_us()
                    send_data = True

                elif ord(msg) == CMD_STOP_WEIGHT_MEAS:
                    print("CMD_STOP_WEIGHT_MEAS")
                    send_data = False

                elif ord(msg) == CMD_TARE_SCALE:
                    print("CMD_TARE_SCALE TODO")

                elif ord(msg) == CMD_START_PEAK_RFD_MEAS:
                    print("CMD_START_PEAK_RFD_MEAS TODO")

                elif ord(msg) == CMD_START_PEAK_RFD_MEAS_SERIES:
                    print("CMD_START_PEAK_RFD_MEAS_SERIES TODO")

                elif ord(msg) == CMD_ADD_CALIBRATION_POINT:
                    print("CMD_ADD_CALIBRATION_POINT TODO")

                elif ord(msg) == CMD_SAVE_CALIBRATION:
                    print("CMD_SAVE_CALIBRATION TODO")

                elif ord(msg) == CMD_GET_ERROR_INFORMATION:
                    print("CMD_GET_ERROR_INFORMATION TODO")

                elif ord(msg) == CMD_CLR_ERROR_INFORMATION:
                    print("CMD_CLR_ERROR_INFORMATION TODO")

                elif ord(msg) == CMD_ENTER_SLEEP:
                    print("CMD_ENTER_SLEEP")
                    send_data = False

                elif ord(msg) == CMD_GET_APP_VERSION:
                    print("CMD_GET_APP_VERSION")
                    control_characteristic.notify(connection, b"1")

                else:
                    print(f"Comando desconocido: {ord(msg)}")

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
            send_data = False


# Run both tasks.
async def main():
    await peripheral_task()


asyncio.run(main())
