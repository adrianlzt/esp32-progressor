#!/usr/bin/env python3

import asyncio
import struct

from aioconsole import ainput
from bleak import BleakClient, BleakScanner
from bleak import discover


TARGET_NAME = "Progressor"

CMD_TARE_SCALE = 100
CMD_START_WEIGHT_MEAS = 101
CMD_STOP_WEIGHT_MEAS = 102
CMD_START_PEAK_RFD_MEAS = 103
CMD_START_PEAK_RFD_MEAS_SERIES = 104
CMD_ADD_CALIBRATION_POINT = 105
CMD_SAVE_CALIBRATION = 106
CMD_GET_APP_VERSION = 107
CMD_GET_ERROR_INFORMATION = 108
CMD_CLR_ERROR_INFORMATION = 109
CMD_ENTER_SLEEP = 110

RES_CMD_RESPONSE = 0
RES_WEIGHT_MEAS = 1
RES_RFD_PEAK = 2
RES_RFD_PEAK_SERIES = 3
RES_LOW_PWR_WARNING = 4

progressor_uuids = {
    "7e4e1701-1ea6-40c9-9dcc-13d34ffead57": "Progressor Service",
    "7e4e1702-1ea6-40c9-9dcc-13d34ffead57": "Data",
    "7e4e1703-1ea6-40c9-9dcc-13d34ffead57": "Control point",
}

progressor_uuids = {v: k for k, v in progressor_uuids.items()}

PROGRESSOR_SERVICE_UUID = "{}".format(
    progressor_uuids.get("Progressor Service")
)
DATA_CHAR_UUID = "{}".format(
    progressor_uuids.get("Data")
)
CTRL_POINT_CHAR_UUID = "{}".format(
    progressor_uuids.get("Control point")
)


def notification_handler(sender, data):
    """ Function for handling data from the Progressor """
    try:
        # print(f"Received data: {data}")
        if data[0] == RES_WEIGHT_MEAS:
            length = data[1]
            # Format is T, L, value, time.
            # To unpack TL, use "<fI" format string.
            # Read all the data until length is finished
            for i in range(0, length, 8):
                value, time = struct.unpack('<fI', data[i+2:i+10])
                print(f"Received weight measurement: {value} kg, time: {time/1000} ms")

        elif data[0] == RES_LOW_PWR_WARNING:
            print("Received low battery warning.")
    except Exception as e:
        print(e)
        raise e


async def run():
    devices = await BleakScanner.discover(timeout=3) # TODO increase tiemout to 5s
    for d in devices:
        if d.name[:len(TARGET_NAME)] == TARGET_NAME:
            if (await ainput(f"Connect to this device {d.name}? [Y/n]: ")).lower() != "n":
                address = d.address
                break
    else:
        print("No more devices found.")
        return

    async with BleakClient(address) as client:
        print(f"Connected: {client.is_connected}")

        await client.start_notify(DATA_CHAR_UUID, notification_handler)

        # Ask the user if he wants to calibrate the scale or just measure weights
        if (await ainput("Do you want to calibrate the scale? [Y/n]: ")).lower() != "n":

            # Ask the user for the weight loaded on the scale
            weight = float(await ainput("Enter the weight loaded on the scale: "))
            # Use struct.pack to convert the weight to a byte array
            weight_bytes = struct.pack('<f', weight)
            # Send this calibration point to the Progressor
            await client.write_gatt_char(CTRL_POINT_CHAR_UUID, [CMD_ADD_CALIBRATION_POINT] + list(weight_bytes))

            # Ask the user for the weight loaded on the scale, for the second time
            weight = float(await ainput("Enter the second weight loaded on the scale: "))
            weight_bytes = struct.pack('<f', weight)
            await client.write_gatt_char(CTRL_POINT_CHAR_UUID, [CMD_ADD_CALIBRATION_POINT] + list(weight_bytes))

            print("Calibrating...")
            await client.write_gatt_char(CTRL_POINT_CHAR_UUID, [CMD_SAVE_CALIBRATION])
            # Get response
            response = await client.read_gatt_char(CTRL_POINT_CHAR_UUID)
            print(f"Response: {response}")

            # Ask the user to remove all weights from the scale and press enter
            await ainput("Remove all weights from the scale and press enter to continue...")

            # Start weight measurements for 1 seconds
            await client.write_gatt_char(CTRL_POINT_CHAR_UUID, [CMD_START_WEIGHT_MEAS])
            response = await client.read_gatt_char(CTRL_POINT_CHAR_UUID)
            print(f"Response: {response}")
            await asyncio.sleep(1)
            await client.write_gatt_char(CTRL_POINT_CHAR_UUID, [CMD_STOP_WEIGHT_MEAS])
            response = await client.read_gatt_char(CTRL_POINT_CHAR_UUID)
            print(f"Response: {response}")

        # Ask the user to load the scale and press enter, or 'q' to exit
        while True:
            if (await ainput("Load the scale and press enter to view one second of measures ('q' to exit): ")).lower() == "q":
                break

            # Start weight measurements for 1 seconds
            await client.write_gatt_char(CTRL_POINT_CHAR_UUID, [CMD_START_WEIGHT_MEAS])
            response = await client.read_gatt_char(CTRL_POINT_CHAR_UUID)
            print(f"Response to start weight measurements: {response}")
            await asyncio.sleep(1)

            print("Stopping weight measurements...")
            await client.write_gatt_char(CTRL_POINT_CHAR_UUID, [CMD_STOP_WEIGHT_MEAS])
            response = await client.read_gatt_char(CTRL_POINT_CHAR_UUID)
            print(f"Response to stop weight measurements: {response}")

            # Some time to print the received data
            await asyncio.sleep(1)

        await client.write_gatt_char(CTRL_POINT_CHAR_UUID, [CMD_ENTER_SLEEP])
        print("Done.")


if __name__ == "__main__":
    asyncio.run(run())
