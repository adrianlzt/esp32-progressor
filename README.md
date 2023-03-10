# ESP32 Progressor

Device used: [Wemos C3 Mini](https://www.wemos.cc/en/latest/c3/c3_mini.html).

## Deploy software

## Flash firmware
Flash [micropython](https://micropython.org/download/LOLIN_C3_MINI/).

[Firmware link](https://micropython.org/resources/firmware/LOLIN_C3_MINI-20220618-v1.19.1.bin)
```
esptool.py --chip esp32c3 --port /dev/ttyACM0 --baud 1000000 write_flash -z 0x0 LOLIN_C3_MINI-20220618-v1.19.1.bin
```

## Install app
Install needed libs:
```
mpremote mip install aioble
mpremote mip install aioble-server
```

Load code:
```
mpremote cp hx711_gpio.py :
mpremote cp main.py :
```

Reset device and connect from the mobile App.
