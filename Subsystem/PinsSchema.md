# PinsSchema.md
# Current hardware schema for ESP32-S3 WROOM CAM system

version: 1.0
target: ESP32-S3-WROOM-CAM

notes:
  - All grounds must be common
  - All voltages are DC
  - Ceramic capacitors are non-polar
  - Electrolytic capacitors are polarized (+ to VCC, - to GND)

# ============================================================
# POWER RAILS
# ============================================================

power:
  rails:
    - name: 5V_MAIN
      voltage: 5V
      source: DC-DC
    - name: 3V3_MAIN
      voltage: 3.3V
      source: DC-DC
    - name: 3V3_MOTOR
      voltage: 3.0-3.3V
      source: DC-DC

# ============================================================
# ESP32
# ============================================================

esp32:
  model: ESP32-S3-WROOM-CAM
  power:
    vin: 5V_MAIN
    gnd: GND
  decoupling:
    - type: ceramic
      value: 100nF
      placement: near_vin
    - type: electrolytic
      value: 10uF
      placement: near_vin

# ============================================================
# CAMERA (FIXED)
# ============================================================

camera:
  model: OV5640
  pins:
    XCLK: GPIO15
    SIOD: GPIO4
    SIOC: GPIO5
    Y9: GPIO16
    Y8: GPIO17
    Y7: GPIO18
    Y6: GPIO12
    Y5: GPIO10
    Y4: GPIO8
    Y3: GPIO9
    Y2: GPIO11
    VSYNC: GPIO6
    HREF: GPIO7
    PCLK: GPIO13

# ============================================================
# I2S MICROPHONE
# ============================================================

inmp441:
  interface: I2S
  pins:
    VDD: 3V3_MAIN
    GND: GND
    SCK: GPIO48
    WS: GPIO47
    SD: GPIO21
    LR: GND
  decoupling:
    - type: ceramic
      value: 100nF
      placement: near_vdd
    - type: electrolytic
      value: 10uF
      placement: near_vdd

# ============================================================
# DAC PCM5102
# ============================================================

pcm5102:
  interface: I2S
  pins:
    VCC: 3V3_MAIN
    GND: GND
    BCLK: GPIO38
    LRCK: GPIO39
    DIN: GPIO40
    MCLK: NC
  output:
    L: pam8403.L_IN
    R: pam8403.R_IN
    GND: GND
  decoupling:
    - type: ceramic
      value: 100nF
      placement: near_vcc
    - type: electrolytic
      value: 10uF
      placement: near_vcc

# ============================================================
# AUDIO AMPLIFIER
# ============================================================

pam8403:
  power:
    VCC: 5V_MAIN
    GND: GND
  input:
    L: pcm5102.L
    R: pcm5102.R
  decoupling:
    - type: ceramic
      value: 100nF
      placement: near_vcc
    - type: electrolytic
      value: 220uF
      placement: near_vcc

# ============================================================
# LIGHT SENSOR
# ============================================================

temt6000:
  pins:
    VCC: 3V3_MAIN
    GND: GND
    OUT: GPIO1
  decoupling:
    - type: ceramic
      value: 100nF
      placement: near_vcc
    - type: electrolytic
      value: 10uF
      placement: near_vcc

# ============================================================
# MOTION SENSOR
# ============================================================

bte16_19:
  pins:
    VCC: 3V3_MAIN
    GND: GND
    OUT: GPIO2
  decoupling:
    - type: ceramic
      value: 100nF
      placement: near_vcc

# ============================================================
# I2C PWM CONTROLLER
# ============================================================

pca9685:
  interface: I2C
  pins:
    VCC: 3V3_MAIN
    GND: GND
    SDA: GPIO43
    SCL: GPIO44
    VPLUS: 3V3_MAIN
  decoupling:
    - type: ceramic
      value: 100nF
      placement: near_vcc
    - type: electrolytic
      value: 22uF
      placement: near_vcc
  pullups:
    - line: SDA
      value: 4.7k
      to: 3V3_MAIN
      optional: true
    - line: SCL
      value: 4.7k
      to: 3V3_MAIN
      optional: true

# ============================================================
# ETHERNET W5500
# ============================================================

w5500:
  interface: SPI
  pins:
    VCC: 3V3_MAIN
    GND: GND
    SCK: GPIO14
    MISO: GPIO46
    MOSI: GPIO42
    CS: GPIO41
    INT: NC
    RST: NC
  notes:
    - MI (Module Input) = ESP MISO (GPIO46)
    - MO (Module Output) = ESP MOSI (GPIO42)
    - INT not connected, polling mode
    - RST pulled to 3V3 via 10K

# ============================================================
# MOSFET CHANNEL (GENERIC)
# ============================================================

mosfet_channel:
  type: AO3400A
  connections:
    gate:
      source: pca9685.channel
      series_resistor: 150R
      pulldown: 10k_to_GND
    drain: load_negative
    source: GND

# ============================================================
# VIBRATION MOTORS
# ============================================================

vibration_motors:
  supply: 3V3_MOTOR
  driver: mosfet_channel
  protection:
    diode:
      type: 1N5819
      cathode: 3V3_MOTOR
      anode: motor_negative
  rail_decoupling:
    - type: ceramic
      value: 100nF
    - type: electrolytic
      value: 470uF

# ============================================================
# LED STRIPS
# ============================================================

led_strips:
  supply: 3V3_MAIN
  driver: mosfet_channel
  decoupling:
    - type: ceramic
      value: 100nF
    - type: electrolytic
      value: 150uF

# ============================================================
# DC-DC MODULES
# ============================================================

dcdc:
  input:
    - type: ceramic
      value: 100nF
    - type: electrolytic
      value: 330uF
  output:
    - type: ceramic
      value: 100nF
    - type: electrolytic
      value: 330uF

# ============================================================
# GLOBAL RULES
# ============================================================

rules:
  - all_gnd_common: true
  - ceramic_near_pins: true
  - electrolytic_near_load: true
  - motor_lines_isolated: true
  - no_direct_load_on_gpio: true