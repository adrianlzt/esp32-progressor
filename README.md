# ESP32 Progressor

DIY strength analyzer for climbing.


## Controller

Device used: [Wemos C3 Mini](https://www.wemos.cc/en/latest/c3/c3_mini.html).

### Flash firmware
Flash [micropython](https://micropython.org/download/LOLIN_C3_MINI/).

[Firmware link](https://micropython.org/resources/firmware/LOLIN_C3_MINI-20220618-v1.19.1.bin)
```
esptool.py --chip esp32c3 --port /dev/ttyACM0 --baud 1000000 write_flash -z 0x0 LOLIN_C3_MINI-20220618-v1.19.1.bin
```

### Install app
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

### Calibrate
Each cell should be calibrated to give accurate results.

There are two values to be calibrated, scale and offset.

To give a weight in kg the device makes a _raw_ measurement and then uses the formula: ``(raw_meas - offset) * scale``.

To calibrate the device we can use the app ``progressor_calibrate.py``:
```
pipenv install
pipenv run progressor_calibrate.py
```

And follow the instructions.

It will ask to put two different known weights on the device and put that value in this app.
With those two measures it will calculate the scale and offset, and store it for future uses.


## S type load cell
This element will be placed between the anchor and our hangboard (or the hold we use) to measure the force.

I bought [this one](https://www.amazon.fr/dp/B077YFF6VQ/ref=pe_3044141_189395771_TE_dp_1) in Amazon.

I guess any brand selling PSD-S1 will work.

I chose 300kg because 100kg is not enough and 2000kg will have a bigger error.

### HX711
To connect the load cell to the WemosC3 we need an ADC (analog-digital converter).

[HX711](https://cdn.sparkfun.com/datasheets/Sensors/ForceFlex/hx711_english.pdf) is an unexpensive ADC specifically designed to weight scales.

It should be configured to do 80 SPS (samplings per second), by default it is normally configured to do 10.

Not all boards allow to change from 10 to 80 SPS.
For example [this one](https://www.ebay.es/itm/HX711-Board-Chip-Waage-Gewichts-sensor-Scale-Modul-Arduino-Raspberry-Pi-Gewicht-/252712602933)
needs a modification, which is complicated (check [here](https://github.com/adrianlzt/piclimbing/blob/master/README.md#:~:text=modify%20the%20board%20slightly) if you need
to do that modification).

It is better to buy a board ready to be changed to 80 SPS, like [this one](https://www.sparkfun.com/products/13879).

To connect the WemosC3 to the HX711:
```
3v3    - Vcc
GPIO   - DT
GPIO   - SCK
GPIO   - GND
```

To connect the load cell to the HX711:
```
Red   - E+
Black - E-
White - A-
Green - A+
```


## Android App
We can use the official Progressor mobile app to get the readings.

### Caveats
The "Tare" button in the phone app does not send any command to the device, it just make the calibration internally
and save the results for future connections.
