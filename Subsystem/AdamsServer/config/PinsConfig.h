/*************** ESP32S3 N16R8 WROOM CAM РАСПИНОВКА МОДУЛЕЙ *****************/


/*********************** КАМЕРА OV5640 **********************/

#define PWDN_GPIO_NUM  -1
#define RESET_GPIO_NUM -1

#define XCLK_GPIO_NUM  15
#define SIOD_GPIO_NUM  4
#define SIOC_GPIO_NUM  5

#define Y9_GPIO_NUM    16
#define Y8_GPIO_NUM    17
#define Y7_GPIO_NUM    18
#define Y6_GPIO_NUM    12
#define Y5_GPIO_NUM    10
#define Y4_GPIO_NUM    8
#define Y3_GPIO_NUM    9
#define Y2_GPIO_NUM    11

#define VSYNC_GPIO_NUM 6
#define HREF_GPIO_NUM  7
#define PCLK_GPIO_NUM  13


/*********************** I2S МИКРОФОН INMP441 x1 ************************/

#define I2S_MIC_BCLK   41   // SCK / BCLK
#define I2S_MIC_WS     42   // LRCLK / WS
#define I2S_MIC_SD     47   // DATA
// L/R → GND (левый канал)


/*********************** I2S DAC PCM5102 / PCM5102A *********************/

#define I2S_DAC_BCLK   38   // BCLK
#define I2S_DAC_LRCK   39   // LRCK / WS
#define I2S_DAC_DATA   40   // DIN / DATA
// MCLK → GND


/*********************** ДАТЧИКИ ****************************************/

#define LIGHT_SENSOR_PIN   1    // TEMT6000 (ADC)
#define MOTION_SENSOR_PIN  2    // BTE16-19 (digital)


/*********************** I2C PCA9685 ************************************/

#define I2C_SDA_PIN   43
#define I2C_SCL_PIN   44


/*********************** W5500 LITE Ethernet ****************************/
// Шелкография модуля W5500 НОТАЦИЯ ОБРАТНАЯ относительно ESP:
//   MI (Module Input)  = физически ESP MISO (GPIO 46)
//   MO (Module Output) = физически ESP MOSI (GPIO 21)

#define ETH_SPI_SCK   14   // SCK
#define ETH_SPI_MISO  46   // MI22222
#define ETH_SPI_MOSI  21   // MO
#define ETH_SPI_CS    45   // CS

#define ETH_INT       -1   // INT not connected, W5500 works in polling mode
#define ETH_RST       -1   // RST -> 10K Omh -> 3V3

/*********************** НЕ ВЫВЕДЕНЫ НА ЭТУ ПЛАТУ ***********************
 *
 * GPIO33 / 34   — отсутствуют на разъёмах платы
 * GPIO35–37     — заняты внутренней PSRAM, наружу не выведены
 *
 ***********************************************************************/

/*********************** НЕ ИСПОЛЬЗОВАТЬ БЕЗ НЕОБХОДИМОСТИ *************
 *
 * GPIO0        — BOOT
 * GPIO3        — strapping pin
 * GPIO19/20    — USB OTG
 * GPIO45 / 46  — strapping / boot
 * GPIO48       — встроенный WS2812
 *
 ***********************************************************************/
