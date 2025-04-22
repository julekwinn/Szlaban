#include "memory.h"
#include "main.h"
#include <stdio.h>

extern I2C_HandleTypeDef hi2c1;

static bool IsEepromReady(uint32_t Trials)
{
    return (HAL_I2C_IsDeviceReady(&hi2c1, EEPROM_I2C_ADDR, Trials, EEPROM_I2C_TIMEOUT) == HAL_OK);
}

bool Memory_Init(void)
{
    printf("Memory_Init: Sprawdzanie gotowości EEPROM...\r\n");
    if (IsEepromReady(5)) {
        printf("Memory_Init: EEPROM gotowy.\r\n");
        return true;
    } else {
        printf("Memory_Init: BŁĄD - EEPROM nie odpowiada!\r\n");
        return false;
    }
}

bool Memory_ReadCounter(uint8_t* counter_buffer)
{
    HAL_StatusTypeDef status;
    printf("Memory_ReadCounter: Odczyt licznika z adresu 0x%02X...\r\n", EEPROM_COUNTER_ADDRESS);
    status = HAL_I2C_Mem_Read(&hi2c1,
                              EEPROM_I2C_ADDR,
                              EEPROM_COUNTER_ADDRESS,
                              I2C_MEMADD_SIZE_8BIT,
                              counter_buffer,
                              EEPROM_COUNTER_SIZE,
                              EEPROM_I2C_TIMEOUT);
    if (status == HAL_OK) {
        printf("Memory_ReadCounter: Odczyt OK. Wartość: %02X %02X %02X %02X %02X %02X %02X %02X\r\n",
               counter_buffer[0], counter_buffer[1], counter_buffer[2], counter_buffer[3],
               counter_buffer[4], counter_buffer[5], counter_buffer[6], counter_buffer[7]);
        return true;
    } else {
        printf("Memory_ReadCounter: BŁĄD odczytu licznika! Status HAL: %d\r\n", status);
        return false;
    }
}

bool Memory_WriteCounter(const uint8_t* counter_buffer)
{
    HAL_StatusTypeDef status;
    printf("Memory_WriteCounter: Zapis licznika pod adresem 0x%02X. Wartość: %02X %02X %02X %02X %02X %02X %02X %02X\r\n",
           EEPROM_COUNTER_ADDRESS,
           counter_buffer[0], counter_buffer[1], counter_buffer[2], counter_buffer[3],
           counter_buffer[4], counter_buffer[5], counter_buffer[6], counter_buffer[7]);

    status = HAL_I2C_Mem_Write(&hi2c1,
                               EEPROM_I2C_ADDR,
                               EEPROM_COUNTER_ADDRESS,
                               I2C_MEMADD_SIZE_8BIT,
                               (uint8_t*)counter_buffer,
                               EEPROM_COUNTER_SIZE,
                               EEPROM_I2C_TIMEOUT);
    if (status == HAL_OK) {
        printf("Memory_WriteCounter: Transmisja I2C OK. Oczekiwanie na tW (%d ms)...\r\n", EEPROM_WRITE_TIME_MS);
        HAL_Delay(EEPROM_WRITE_TIME_MS);
        if (!IsEepromReady(2)) {
             printf("Memory_WriteCounter: UWAGA - EEPROM nie potwierdził gotowości po tW.\r\n");
        } else {
             printf("Memory_WriteCounter: Zapis licznika zakończony.\r\n");
        }
        return true;
    } else {
        printf("Memory_WriteCounter: BŁĄD zapisu licznika! Status HAL: %d\r\n", status);
        return false;
    }
}

// --- Nowe funkcje dla flagi inicjalizacji ---

bool Memory_ReadInitFlag(uint8_t* flag_value)
{
    HAL_StatusTypeDef status;
    printf("Memory_ReadInitFlag: Odczyt flagi z adresu 0x%02X...\r\n", EEPROM_INIT_FLAG_ADDRESS);
    status = HAL_I2C_Mem_Read(&hi2c1,
                              EEPROM_I2C_ADDR,
                              EEPROM_INIT_FLAG_ADDRESS,
                              I2C_MEMADD_SIZE_8BIT, // Adres flagi też ma 1 bajt
                              flag_value,           // Odczytaj 1 bajt
                              1,
                              EEPROM_I2C_TIMEOUT);
    if (status == HAL_OK) {
        printf("Memory_ReadInitFlag: Odczyt OK. Wartość flagi: 0x%02X\r\n", *flag_value);
        return true;
    } else {
        printf("Memory_ReadInitFlag: BŁĄD odczytu flagi! Status HAL: %d\r\n", status);
        return false;
    }
}

bool Memory_WriteInitFlag(uint8_t flag_value)
{
    HAL_StatusTypeDef status;
    printf("Memory_WriteInitFlag: Zapis flagi pod adresem 0x%02X. Wartość: 0x%02X\r\n",
           EEPROM_INIT_FLAG_ADDRESS, flag_value);

    status = HAL_I2C_Mem_Write(&hi2c1,
                               EEPROM_I2C_ADDR,
                               EEPROM_INIT_FLAG_ADDRESS,
                               I2C_MEMADD_SIZE_8BIT,
                               &flag_value,       // Zapisz 1 bajt
                               1,
                               EEPROM_I2C_TIMEOUT);
    if (status == HAL_OK) {
        printf("Memory_WriteInitFlag: Transmisja I2C OK. Oczekiwanie na tW (%d ms)...\r\n", EEPROM_WRITE_TIME_MS);
        HAL_Delay(EEPROM_WRITE_TIME_MS); // Odczekaj tW także po zapisie flagi
         if (!IsEepromReady(2)) {
             printf("Memory_WriteInitFlag: UWAGA - EEPROM nie potwierdził gotowości po tW.\r\n");
        } else {
             printf("Memory_WriteInitFlag: Zapis flagi zakończony.\r\n");
        }
        return true;
    } else {
        printf("Memory_WriteInitFlag: BŁĄD zapisu flagi! Status HAL: %d\r\n", status);
        return false;
    }
}
