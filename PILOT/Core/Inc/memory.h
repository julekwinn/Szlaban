#ifndef INC_MEMORY_H_
#define INC_MEMORY_H_

#include <stdint.h>
#include <stdbool.h>

// --- Konfiguracja EEPROM ---
#define EEPROM_I2C_ADDRESS_7BIT  0x50
#define EEPROM_I2C_ADDR          (EEPROM_I2C_ADDRESS_7BIT << 1)

// Adres licznika (8 bajtów)
#define EEPROM_COUNTER_ADDRESS   0x00
#define EEPROM_COUNTER_SIZE      8

// Adres flagi inicjalizacji (1 bajt) - umieszczony PO liczniku
#define EEPROM_INIT_FLAG_ADDRESS (EEPROM_COUNTER_ADDRESS + EEPROM_COUNTER_SIZE) // Adres 0x08
#define EEPROM_INIT_FLAG_VALUE   0xAA // Oczekiwana wartość flagi po inicjalizacji

// Timeout dla operacji I2C w milisekundach
#define EEPROM_I2C_TIMEOUT       100 // ms

// Czas zapisu wewnętrznego EEPROM (tW) w milisekundach
#define EEPROM_WRITE_TIME_MS     5

// --- Deklaracje funkcji ---

bool Memory_Init(void);
bool Memory_ReadCounter(uint8_t* counter_buffer);
bool Memory_WriteCounter(const uint8_t* counter_buffer);

/**
 * @brief Odczytuje flagę inicjalizacji z EEPROM.
 * @param flag_value Wskaźnik do zmiennej, gdzie zostanie zapisana odczytana flaga.
 * @retval true jeśli odczyt zakończył się sukcesem, false w przypadku błędu.
 */
bool Memory_ReadInitFlag(uint8_t* flag_value);

/**
 * @brief Zapisuje flagę inicjalizacji do EEPROM.
 * @param flag_value Wartość flagi do zapisania.
 * @retval true jeśli zapis zakończył się sukcesem, false w przypadku błędu.
 */
bool Memory_WriteInitFlag(uint8_t flag_value);

#endif /* INC_MEMORY_H_ */
