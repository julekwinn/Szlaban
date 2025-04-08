/* Define to prevent recursive inclusion */
#ifndef __I2C_UTILS_H
#define __I2C_UTILS_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include <stdio.h>

/* Exported functions prototypes ---------------------------------------------*/
/**
 * @brief Skanuje magistralę I2C w poszukiwaniu podłączonych urządzeń
 * @param hi2c: Wskaźnik do struktury handlera I2C
 * @return Liczba znalezionych urządzeń
 */
uint8_t I2C_Scan(I2C_HandleTypeDef *hi2c);

/**
 * @brief Wyświetla mapę urządzeń I2C w formacie siatki 16x8
 */
void I2C_PrintDeviceMap(void);

#ifdef __cplusplus
}
#endif

#endif /* __I2C_UTILS_H */
