#define CONFIG_H

#include "main.h"
#include <stdint.h>

/* Identyfikator pilota (8 bajtów) */
#define PILOT_ID_LENGTH 8
extern const uint8_t PILOT_ID[PILOT_ID_LENGTH];

/* Konfiguracja kluczy kryptograficznych */
#define CRYPTO_AES_KEY_LENGTH 16
#define CRYPTO_HMAC_KEY_LENGTH 32  // Typowo klucz HMAC jest dłuższy dla SHA-256
#define CRYPTO_IV_LENGTH 16

/* Klucz AES (16 bajtów) */
extern const uint8_t CRYPTO_AES_KEY[CRYPTO_AES_KEY_LENGTH];

/* Klucz HMAC (32 bajty) */
extern const uint8_t CRYPTO_HMAC_KEY[CRYPTO_HMAC_KEY_LENGTH];

/* Wektor inicjalizacyjny IV (16 bajtów) */
extern const uint8_t CRYPTO_IV[CRYPTO_IV_LENGTH];

/* Konfiguracja maksymalnych długości */
#define MAX_COMMAND_LENGTH 32
#define MAX_FRAME_SIZE 128

/* Inne ustawienia systemowe */
#define UART_BAUDRATE 115200


