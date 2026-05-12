# ESP32-S3 N16R8 WROOM CAM — Pinout & Hardware Reference

format: ai-md
version: 1.0

---

## DEVICE OVERVIEW

* MCU: ESP32-S3
* Flash: 16MB (N16)
* PSRAM: 8MB (R8)
* Wi-Fi: 2.4 GHz
* Bluetooth: BLE 5
* Logic Level: 3.3V
* Power Input: 5V (VIN / USB)

constraints:

* gpio_max_voltage: 3.3V
* 5v_tolerant: false

---

## POWER SYSTEM

pins:
5V:
type: power_input
description: main supply input

3V3:
type: regulated_output
description: onboard regulator output

GND:
type: ground

rules:

* all_grounds_common: true

---

## RESERVED PINS

camera:
GPIO4: CAM_SIOD
GPIO5: CAM_SIOC
GPIO6: CAM_VSYNC
GPIO7: CAM_HREF
GPIO8: CAM_Y4
GPIO9: CAM_Y3
GPIO10: CAM_Y5
GPIO11: CAM_Y2
GPIO12: CAM_Y6
GPIO13: CAM_PCLK
GPIO15: CAM_XCLK
GPIO16: CAM_Y9
GPIO17: CAM_Y8
GPIO18: CAM_Y7

psram:
GPIO35: RESERVED
GPIO36: RESERVED
GPIO37: RESERVED

usb:
GPIO19: USB_D+
GPIO20: USB_D-

boot:
GPIO0: BOOT_STRAP

---

## AVAILABLE GPIO

usable:

* GPIO1
* GPIO2
* GPIO3
* GPIO14
* GPIO21
* GPIO38
* GPIO39
* GPIO40
* GPIO41
* GPIO42
* GPIO43
* GPIO44
* GPIO45
* GPIO47
* GPIO48

---

## ADC

adc1:
GPIO1: ADC1_CH0
GPIO2: ADC1_CH1
GPIO3: ADC1_CH2

adc2:
GPIO14: ADC2_CH3
GPIO38: ADC2
GPIO39: ADC2

notes:

* adc2_conflict_with_wifi: true

---

## I2C

recommended:
SDA: GPIO43
SCL: GPIO44

configurable: true

---

## I2S CONFIGURATION

output_dac:
BCLK: GPIO38
LRCK: GPIO39
DATA: GPIO40

input_mic:
SCK: GPIO42
WS: GPIO41
SD: GPIO47

---

## UART

uart0:
TX: GPIO43
RX: GPIO44

---

## PWM

available_on:

* GPIO1
* GPIO2
* GPIO3
* GPIO14
* GPIO21
* GPIO38
* GPIO39
* GPIO40
* GPIO41
* GPIO42
* GPIO43
* GPIO44
* GPIO45
* GPIO47
* GPIO48

engine: LEDC

---

## SPECIAL FUNCTIONS

jtag:
GPIO41: MTDI
GPIO42: MTMS

spi:
GPIO45: VSPI

onboard_led:
GPIO48: optional_ws2812

---

## RESTRICTIONS

rules:

* do_not_use:

  * GPIO0
  * GPIO4-18
  * GPIO19
  * GPIO20
  * GPIO35-37

* avoid_adc2_when_wifi: true

---

## RECOMMENDED ASSIGNMENT MAP

mapping:
i2c:
SDA: GPIO43
SCL: GPIO44

i2s_dac:
BCLK: GPIO38
LRCK: GPIO39
DATA: GPIO40

i2s_mic:
SCK: GPIO42
WS: GPIO41
SD: GPIO47

analog_sensor:
pin: GPIO1

digital_sensor:
pin: GPIO21

---

## ELECTRICAL GUIDELINES

rules:

* decoupling_required: true
* ceramic_caps_near_pins: true
* electrolytic_caps_near_loads: true
* no_direct_high_current_on_gpio: true
* use_mosfet_for_loads: true

---

## DECOUPLING BASELINE

standard:
logic:
- 100nF ceramic per module

audio:
- 100nF + 10uF

power_lines:
- 100nF + 220-470uF

motors:
- 100nF + 470uF

---
