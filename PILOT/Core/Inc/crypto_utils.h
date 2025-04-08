#define CRYPTO_UTILS_H

#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "cmox_crypto.h" // Główny plik nagłówkowy biblioteki kryptograficznej
#include "config.h" // Dodane odwołanie do pliku konfiguracyjnego

/* Funkcje demonstracyjne */
void text_hashing_example(void);
void text_aes_encode(void);
void text_aes_decode_example(void);

/* Funkcja konwersji binarnej na heksadecymalną */
void btox(uint8_t *hexbuf, const uint8_t *binbuf, int n);

/* Funkcja tworząca ramkę danych do wysyłki */
void create_secure_command_frame(const uint8_t *pilot_id, const uint8_t *counter,
                               const uint8_t *aes_key, size_t aes_key_size,
                               const uint8_t *hmac_key, size_t hmac_key_size,
                               const uint8_t *iv, size_t iv_size,
                               uint8_t *output, size_t *output_size);

/* Funkcja walidująca odebrane dane */
uint8_t validate_and_process_command(const uint8_t *received_data, size_t data_size,
                                   const uint8_t *aes_key, size_t aes_key_size,
                                   const uint8_t *hmac_key, size_t hmac_key_size,
                                   const uint8_t *iv, size_t iv_size,
                                   uint8_t *output_pilot_id, uint8_t *output_counter,
                                   uint8_t *output_command, size_t *output_command_size);


