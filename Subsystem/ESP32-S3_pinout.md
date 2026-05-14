# ESP32-S3 WROOM CAM — Full Pinout Reference

---

# LEFT SIDE PINS

GPIO4:
functions:
- CAM_SIOD
- ADC1_CH3
- TOUCH4
reserved_for_camera: true

GPIO5:
functions:
- CAM_SIOC
- ADC1_CH4
- TOUCH5
reserved_for_camera: true

GPIO6:
functions:
- CAM_VSYNC
- ADC1_CH5
- TOUCH6
reserved_for_camera: true

GPIO7:
functions:
- CAM_HREF
- ADC1_CH6
- TOUCH7
reserved_for_camera: true

GPIO15:
functions:
- CAM_XCLK
- ADC2_CH4
- U0RTS
reserved_for_camera: true

GPIO16:
functions:
- CAM_Y9
- ADC2_CH5
- U0CTS
reserved_for_camera: true

GPIO17:
functions:
- CAM_Y8
- ADC2_CH6
- U1TXD
reserved_for_camera: true

GPIO18:
functions:
- CAM_Y7
- ADC2_CH7
- U1RXD
reserved_for_camera: true

GPIO8:
functions:
- CAM_Y4
- ADC1_CH7
- TOUCH8
reserved_for_camera: true

GPIO3:
functions:
- JTAG_EN
- ADC1_CH2
- TOUCH3
reserved_for_camera: false

GPIO46:
functions:
- GPIO
- LOG_UART
- DEBUG
input_only: true

GPIO9:
functions:
- CAM_Y3
- ADC1_CH8
- TOUCH9
reserved_for_camera: true

GPIO10:
functions:
- CAM_Y5
- ADC1_CH9
- TOUCH10
reserved_for_camera: true

GPIO11:
functions:
- CAM_Y2
- ADC2_CH0
- TOUCH11
reserved_for_camera: true

GPIO12:
functions:
- CAM_Y6
- ADC2_CH1
- TOUCH12
reserved_for_camera: true

GPIO13:
functions:
- CAM_PCLK
- ADC2_CH2
- TOUCH13
reserved_for_camera: true

GPIO14:
functions:
- ADC2_CH3
- TOUCH14
reserved_for_camera: false

3V3:
type: power
voltage: 3.3V

RST:
type: reset

5V:
type: power
voltage: 5V

---

# RIGHT SIDE PINS

GPIO43:
functions:
- U0TXD
- LED_TX
recommended_usage:
- I2C_SDA
- UART_TX

GPIO44:
functions:
- U0RXD
- LED_RX
recommended_usage:
- I2C_SCL
- UART_RX

GPIO1:
functions:
- ADC1_CH0
- TOUCH1
recommended_usage:
- analog_sensor

GPIO2:
functions:
- ADC1_CH1
- TOUCH2
- LED_ON
recommended_usage:
- digital_io

GPIO42:
functions:
- MTMS
recommended_usage:
- I2S_SCK
- SPI_MISO

GPIO41:
functions:
- MTDI
recommended_usage:
- I2S_WS
- SPI_MOSI

GPIO40:
functions:
- SD_DATA
- MTDO
recommended_usage:
- I2S_DATA

GPIO39:
functions:
- SD_CLK
recommended_usage:
- I2S_LRCK

GPIO38:
functions:
- SD_CMD
- MTCK
recommended_usage:
- I2S_BCLK

GPIO37:
functions:
- PSRAM
reserved_internal: true

GPIO36:
functions:
- PSRAM
reserved_internal: true

GPIO35:
functions:
- PSRAM
reserved_internal: true

GPIO0:
functions:
- BOOT
dangerous_for_general_io: true

GPIO45:
functions:
- VSPI
recommended_usage:
- SPI_SCK

GPIO48:
functions:
- WS2812
recommended_usage:
- onboard_led

GPIO47:
functions:
- GPIO
recommended_usage:
- I2S_MIC_SD
- PWM

GPIO21:
functions:
- GPIO
recommended_usage:
- motion_sensor
- PWM

GPIO20:
functions:
- USB_D-
- ADC2_CH9
- U1CTS
reserved_for_usb: true

GPIO19:
functions:
- USB_D+
- ADC2_CH8
- U1RTS
reserved_for_usb: true

GND:
type: ground

---

# INTERNAL RESERVATIONS

reserved:
camera:
- GPIO4
- GPIO5
- GPIO6
- GPIO7
- GPIO8
- GPIO9
- GPIO10
- GPIO11
- GPIO12
- GPIO13
- GPIO15
- GPIO16
- GPIO17
- GPIO18

psram:
- GPIO35
- GPIO36
- GPIO37

usb:
- GPIO19
- GPIO20

---

# SAFE GPIO SUMMARY

safe_gpio:

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

# SPECIAL NOTES

notes:

* GPIO46 is input only
* GPIO0 affects boot mode
* GPIO19 and GPIO20 reserved for USB
* GPIO35-37 reserved for PSRAM
* GPIO4-18 occupied by camera
* all GPIO logic levels are 3.3V
* GPIO are NOT 5V tolerant

---