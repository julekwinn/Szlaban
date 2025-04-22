/* Includes ------------------------------------------------------------------*/
#include "i2c_utils.h"

/* Private define ------------------------------------------------------------*/
#define I2C_SCAN_TIMEOUT 10  /* Timeout dla sprawdzania urządzeń w ms */

/* Private variables ---------------------------------------------------------*/
static uint8_t active_devices[128];  /* Tablica aktywnych urządzeń (0-127) */
static uint8_t device_count = 0;     /* Liczba znalezionych urządzeń */

/**
 * @brief Skanuje magistralę I2C w poszukiwaniu podłączonych urządzeń
 * @param hi2c: Wskaźnik do struktury handlera I2C
 * @return Liczba znalezionych urządzeń
 */
uint8_t I2C_Scan(I2C_HandleTypeDef *hi2c) {
    HAL_StatusTypeDef status;
    device_count = 0;

    /* Wyzeruj tablicę aktywnych urządzeń */
    for (uint8_t i = 0; i < 128; i++) {
        active_devices[i] = 0;
    }

    printf("\r\n--- Rozpoczynam skanowanie magistrali I2C ---\r\n");

    /* Skanowanie wszystkich możliwych adresów (0-127) */
    for (uint8_t i = 1; i < 128; i++) {  /* Pomijamy adres 0 (broadcast) */
        /* Shift adresu - wymagane przez HAL */
        uint16_t deviceAddr = i << 1;

        /* Sprawdź obecność urządzenia */
        status = HAL_I2C_IsDeviceReady(hi2c, deviceAddr, 3, I2C_SCAN_TIMEOUT);

        /* Jeśli urządzenie odpowiada */
        if (status == HAL_OK) {
            printf("  [ZNALEZIONO] Urzadzenie pod adresem: 0x%02X\r\n", i);
            active_devices[i] = 1;
            device_count++;
        }
    }

    printf("\r\nZnaleziono %d urzadzen I2C.\r\n", device_count);

    /* Wyświetl mapę urządzeń w formie siatki */
    if (device_count > 0) {
        I2C_PrintDeviceMap();
    }

    printf("--- Skanowanie zakonczone ---\r\n\n");

    return device_count;
}

/**
 * @brief Wyświetla mapę urządzeń I2C w formacie siatki 16x8
 */
void I2C_PrintDeviceMap(void) {
    printf("\r\n--- Mapa urzadzen I2C ---\r\n");
    printf("       0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F\r\n");

    for (uint8_t row = 0; row < 8; row++) {
        printf("0x%X0: ", row);

        for (uint8_t col = 0; col < 16; col++) {
            uint8_t addr = row * 16 + col;

            if (active_devices[addr]) {
                printf(" X ");  /* Urządzenie znalezione */
            } else {
                printf(" . ");  /* Brak urządzenia */
            }
        }
        printf("\r\n");
    }

    printf("-----------------------------------\r\n");
    printf("Legenda: X = urzadzenie znalezione, . = brak urzadzenia\r\n");
    printf("-----------------------------------\r\n");
}
