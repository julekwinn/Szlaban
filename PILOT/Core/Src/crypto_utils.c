/*
 * File: crypto_utils.c
 * Description: Implementacja funkcji kryptograficznych
 */

#include "crypto_utils.h"
#include <stdio.h>
#include <string.h>
#include "main.h"
#include "config.h"  // Dodane odwołanie do pliku konfiguracyjnego
#include "cmox_crypto.h"  // Główny plik nagłówkowy biblioteki kryptograficznej

/* Function to convert binary to hex string */
void btox(uint8_t *hexbuf, const uint8_t *binbuf, int n)
{
    n *= 2;
    hexbuf[n] = 0x00;       // string null termination
    const char hex[]= "0123456789abcdef";
    while (--n >= 0)
        hexbuf[n] = hex[(binbuf[n>>1] >> ((1 - (n&1)) << 2)) & 0xF];
}

/* Implementacja funkcji haszującej przykład */
void text_hashing_example(void)
{
    cmox_hash_retval_t retval;
    uint8_t data[] = "Alice has a cat.";
    uint8_t hash[CMOX_SHA256_SIZE];
    size_t computed_size;
    uint8_t buffer[2*CMOX_SHA256_SIZE+1];

    /* Initialize cryptographic library */
    if (cmox_initialize(NULL) != CMOX_INIT_SUCCESS)
        Error_Handler();

    retval = cmox_hash_compute(CMOX_SHA256_ALGO,             /* Use SHA256 algorithm */
                              data, strlen((char*)data),      /* Message to digest */
                              hash,                           /* Data buffer to receive digest data */
                              CMOX_SHA256_SIZE,               /* Expected digest size */
                              &computed_size);                /* Size of computed digest */

    /* Verify API returned value */
    if (retval != CMOX_HASH_SUCCESS)
        Error_Handler();

    printf("Input data (ASCII): %s (length=%d)\n\r", data, strlen((char*)data));
    btox(buffer, data, strlen((char*)data));
    printf("Input data (hex)  : %s\n\r", buffer);

    printf("Hash (ASCII): %s\n\r", hash);    // risky!!! null-termination may not exist
    btox(buffer, hash, CMOX_SHA256_SIZE);
    printf("Hash (hex)  : %s\n\r", buffer);

    /* Cleanup the cryptographic library */
    if (cmox_finalize(NULL) != CMOX_INIT_SUCCESS)
        Error_Handler();
}

/* Implementacja funkcji szyfrowania AES */
void text_aes_encode(void)
{
    cmox_cipher_retval_t retval;
    size_t computed_size;
    uint8_t Plaintext[] = "This is my secret"; // Tekst do zaszyfrowania
    uint8_t Ciphertext[sizeof(Plaintext)];
    uint8_t buffer[2*sizeof(Plaintext)+1];

    btox(buffer, Plaintext, sizeof(Plaintext) - 1); // -1 aby pominąć znak null
    printf("Plaintext as hexstring: %s\n\r", buffer);
    printf("Plaintext: %s\n\r", Plaintext);

    /* Initialize cryptographic library */
    if (cmox_initialize(NULL) != CMOX_INIT_SUCCESS)
        Error_Handler();

    /* Compute directly the ciphertext passing all the needed parameters */
    retval = cmox_cipher_encrypt(CMOX_AESFAST_CTR_ENC_ALGO,           /* Use AES CTR algorithm */
                               Plaintext, sizeof(Plaintext) - 1,       /* Plaintext to encrypt, -1 to exclude null terminator */
                               CRYPTO_AES_KEY, sizeof(CRYPTO_AES_KEY), /* AES key to use z pliku config */
                               CRYPTO_IV, sizeof(CRYPTO_IV),           /* Initialization vector z pliku config */
                               Ciphertext, &computed_size);            /* Data buffer to receive generated ciphertext */

    /* Verify API returned value */
    if (retval != CMOX_CIPHER_SUCCESS)
        Error_Handler();

    /* Print the ciphertext */
    btox(buffer, Ciphertext, computed_size);
    printf("Ciphertext as hexstring: %s\n\r", buffer);

    btox(buffer, CRYPTO_IV, sizeof(CRYPTO_IV));
    printf("IV: %s\n\r", buffer);

    btox(buffer, CRYPTO_AES_KEY, sizeof(CRYPTO_AES_KEY));
    printf("Key: %s\n\r", buffer);

    /* Cleanup the cryptographic library */
    if (cmox_finalize(NULL) != CMOX_INIT_SUCCESS)
        Error_Handler();
}

/* Implementacja funkcji deszyfrowania AES */
void text_aes_decode_example(void)
{
    cmox_cipher_retval_t retval;
    size_t computed_size;
    uint8_t Ciphertext[] = { 0x90, 0x34, 0x4c, 0x02, 0xc2, 0x2f, 0x90, 0xd8,
                             0x25, 0x5d, 0xa3, 0x0d, 0x5c, 0x23, 0x97, 0x27,
                             0x04, 0xbb, 0x44, 0x04 };
    uint8_t Computed_Plaintext[sizeof(Ciphertext) + 1];  // +1 na znak null-terminator
    uint8_t buffer[2*sizeof(Computed_Plaintext)+1];

    btox(buffer, Ciphertext, sizeof(Ciphertext));
    printf("Ciphertext as hexstring: %s\n\r", buffer);

    /* Initialize cryptographic library */
    if (cmox_initialize(NULL) != CMOX_INIT_SUCCESS)
        Error_Handler();

    /* Compute directly the plaintext passing all the needed parameters */
    retval = cmox_cipher_decrypt(CMOX_AESFAST_CTR_DEC_ALGO,           /* Use AES CTR algorithm */
                               Ciphertext, sizeof(Ciphertext),        /* Ciphertext to decrypt */
                               CRYPTO_AES_KEY, sizeof(CRYPTO_AES_KEY), /* AES key to use z pliku config */
                               CRYPTO_IV, sizeof(CRYPTO_IV),          /* Initialization vector z pliku config */
                               Computed_Plaintext, &computed_size);   /* Data buffer to receive generated plaintext */

    /* Verify API returned value */
    if (retval != CMOX_CIPHER_SUCCESS)
        Error_Handler();

    /* Ensure the plaintext is null-terminated for safe printing */
    Computed_Plaintext[computed_size] = '\0';

    printf("Computed plaintext: %s\n\r", Computed_Plaintext);
    btox(buffer, Computed_Plaintext, computed_size);
    printf("Plaintext as hexstring: %s\n\r", buffer);

    btox(buffer, CRYPTO_IV, sizeof(CRYPTO_IV));
    printf("IV: %s\n\r", buffer);

    btox(buffer, CRYPTO_AES_KEY, sizeof(CRYPTO_AES_KEY));
    printf("Key: %s\n\r", buffer);

    /* Cleanup the cryptographic library */
    if (cmox_finalize(NULL) != CMOX_INIT_SUCCESS)
        Error_Handler();
}

/* Funkcja walidująca odebrane dane */
uint8_t validate_and_process_command(const uint8_t *received_data, size_t data_size,
                                   const uint8_t *aes_key, size_t aes_key_size,
                                   const uint8_t *hmac_key, size_t hmac_key_size,
                                   const uint8_t *iv, size_t iv_size,
                                   uint8_t *output_pilot_id, uint8_t *output_counter,
                                   uint8_t *output_command, size_t *output_command_size)
{
    cmox_cipher_retval_t cipher_retval;
    cmox_mac_retval_t mac_retval;
    size_t computed_size;
    uint8_t result = 0; // 0 = błąd, 1 = sukces

    /* Bufory na dane */
    uint8_t encrypted_frame[MAX_FRAME_SIZE];               // Bufor na zaszyfrowaną ramkę
    uint8_t received_hmac[CMOX_SHA256_SIZE];               // Bufor na otrzymany HMAC
    uint8_t computed_hmac[CMOX_SHA256_SIZE];               // Bufor na obliczony HMAC
    uint8_t decrypted_frame[MAX_FRAME_SIZE];               // Bufor na odszyfrowaną ramkę
    uint8_t buffer[MAX_FRAME_SIZE*2];                      // Bufor pomocniczy na wydruk hex
    size_t computed_hmac_size;

    printf("\n\r===== Walidacja i przetwarzanie odebranej ramki =====\n\r");

    /* Sprawdź minimalny rozmiar danych */
    if (data_size < (16 + CMOX_SHA256_SIZE)) { // 16 bajtów data + HMAC
        printf("Błąd: Otrzymano zbyt mało danych!\n\r");
        return 0;
    }

    /* Rozdziel dane na zaszyfrowaną ramkę i HMAC */
    size_t encrypted_size = data_size - CMOX_SHA256_SIZE;
    memcpy(encrypted_frame, received_data, encrypted_size);
    memcpy(received_hmac, received_data + encrypted_size, CMOX_SHA256_SIZE);

    printf("Otrzymana zaszyfrowana ramka (hex): ");
    btox(buffer, encrypted_frame, encrypted_size);
    printf("%s\n\r", buffer);

    printf("Otrzymany HMAC (hex): ");
    btox(buffer, received_hmac, CMOX_SHA256_SIZE);
    printf("%s\n\r", buffer);

    /* Inicjalizuj bibliotekę kryptograficzną */
    if (cmox_initialize(NULL) != CMOX_INIT_SUCCESS)
        Error_Handler();

    /* 1. Obliczenie HMAC i porównanie z otrzymanym - używając osobnego klucza HMAC */
    printf("\n\r>> Weryfikacja HMAC <<\n\r");

    /* Użyj funkcji cmox_mac_compute z kluczem HMAC */
    mac_retval = cmox_mac_compute(CMOX_HMAC_SHA256_ALGO,            /* Algorytm HMAC-SHA256 */
                              encrypted_frame, encrypted_size,       /* Dane do podpisania */
                              hmac_key, hmac_key_size,               /* Klucz HMAC */
                              NULL, 0,                               /* Brak danych niestandardowych */
                              computed_hmac, CMOX_SHA256_SIZE, &computed_hmac_size);  /* Bufor na podpis HMAC */

    /* Sprawdź czy obliczenie HMAC się powiodło */
    if (mac_retval != CMOX_MAC_SUCCESS)
        Error_Handler();

    /* Wydrukuj obliczony HMAC */
    printf("Obliczony HMAC (hex): ");
    btox(buffer, computed_hmac, computed_hmac_size);
    printf("%s\n\r", buffer);

    /* Porównaj otrzymany HMAC z obliczonym */
    if (memcmp(received_hmac, computed_hmac, CMOX_SHA256_SIZE) != 0) {
        printf("Błąd: Podpis HMAC nie zgadza się! Możliwa manipulacja danymi.\n\r");
        result = 0;  // Błąd weryfikacji HMAC
    } else {
        printf("Weryfikacja HMAC poprawna.\n\r");

        /* 2. Deszyfrowanie ramki przy użyciu klucza AES */
        printf("\n\r>> Deszyfrowanie ramki <<\n\r");

        cipher_retval = cmox_cipher_decrypt(CMOX_AESFAST_CTR_DEC_ALGO,   /* Algorytm AES-CTR */
                                  encrypted_frame, encrypted_size,        /* Zaszyfrowana ramka */
                                  aes_key, aes_key_size,                  /* Klucz AES */
                                  iv, iv_size,                            /* Wektor inicjalizacyjny */
                                  decrypted_frame, &computed_size);       /* Bufor na odszyfrowane dane */

        /* Sprawdź czy deszyfrowanie się powiodło */
        if (cipher_retval != CMOX_CIPHER_SUCCESS) {
            printf("Błąd: Deszyfrowanie nie powiodło się!\n\r");
            result = 0;  // Błąd deszyfrowania
        } else {
            /* Zapewnij null-terminator dla bezpiecznego wydruku */
            decrypted_frame[computed_size] = '\0';

            printf("Odszyfrowana ramka (hex): ");
            btox(buffer, decrypted_frame, computed_size);
            printf("%s\n\r", buffer);

            /* 3. Analiza odszyfrowanej ramki */
            printf("\n\r>> Analiza odszyfrowanej ramki <<\n\r");

            /* Sprawdź czy rozmiar ramki jest wystarczający */
            if (computed_size < 16) {  // co najmniej 8+8 bajtów na ID i licznik
                printf("Błąd: Odszyfrowana ramka jest zbyt mała!\n\r");
                result = 0;  // Błąd rozmiaru ramki
            } else {
                /* Pobierz ID pilota (8 bajtów) */
                memcpy(output_pilot_id, decrypted_frame, PILOT_ID_LENGTH);
                printf("- ID pilota (8B): ");
                btox(buffer, output_pilot_id, PILOT_ID_LENGTH);
                printf("%s\n\r", buffer);

                /* Pobierz licznik (8 bajtów) */
                memcpy(output_counter, decrypted_frame + PILOT_ID_LENGTH, 8);
                printf("- Licznik (8B): ");
                btox(buffer, output_counter, 8);
                printf("%s\n\r", buffer);

                /* Pobierz komendę (reszta danych) */
                size_t command_size = computed_size - 16;  // 16 bajtów to ID + licznik
                if (command_size > 0) {
                    memcpy(output_command, decrypted_frame + 16, command_size);
                    output_command[command_size] = '\0';  // Dodaj null-terminator dla bezpiecznego wydruku
                    *output_command_size = command_size;

                    printf("- Komenda: %s\n\r", output_command);
                    result = 1;  // Wszystko OK
                } else {
                    printf("Ostrzeżenie: Brak komendy w ramce!\n\r");
                    *output_command_size = 0;
                    result = 0;  // Brak komendy
                }
            }
        }
    }

    /* Zwolnij zasoby biblioteki kryptograficznej */
    if (cmox_finalize(NULL) != CMOX_INIT_SUCCESS)
        Error_Handler();

    return result;
}
void create_secure_command_frame(const uint8_t *pilot_id, const uint8_t *counter,
                               const uint8_t *aes_key, size_t aes_key_size,
                               const uint8_t *hmac_key, size_t hmac_key_size,
                               const uint8_t *iv, size_t iv_size,
                               uint8_t *output, size_t *output_size)
{
    cmox_cipher_retval_t cipher_retval;
    cmox_mac_retval_t mac_retval;
    size_t computed_size;
    size_t mac_size;

    /* Stałe dla komendy */
    const uint8_t command[] = "eszp_open";

    /* Bufory na dane */
    uint8_t frame[MAX_FRAME_SIZE];                   // Bufor na ramkę danych
    uint8_t encrypted_frame[MAX_FRAME_SIZE];         // Bufor na zaszyfrowaną ramkę
    uint8_t hmac[CMOX_SHA256_SIZE];                  // Bufor na podpis HMAC
    uint8_t buffer[MAX_FRAME_SIZE*2];                // Bufor pomocniczy na wydruk hex

    /* Utwórz ramkę danych: [pilot_id (8B) | counter (8B) | command (zmienna długość)] */
    size_t frame_size = 0;

    /* Skopiuj ID pilota (8 bajtów) */
    memcpy(frame, pilot_id, PILOT_ID_LENGTH);
    frame_size += PILOT_ID_LENGTH;

    /* Skopiuj licznik (8 bajtów) */
    memcpy(frame + frame_size, counter, 8);
    frame_size += 8;

    /* Skopiuj komendę */
    memcpy(frame + frame_size, command, strlen((char*)command));
    frame_size += strlen((char*)command);

    printf("\n\r===== Tworzenie bezpiecznej ramki danych =====\n\r");

    /* Wyświetl utworzoną ramkę */
    printf("Ramka danych:\n\r");
    printf("- ID pilota (8B): ");
    btox(buffer, pilot_id, PILOT_ID_LENGTH);
    printf("%s\n\r", buffer);

    printf("- Licznik (8B): ");
    btox(buffer, counter, 8);
    printf("%s\n\r", buffer);

    printf("- Komenda: %s\n\r", command);

    printf("Pełna ramka (hex): ");
    btox(buffer, frame, frame_size);
    printf("%s\n\r", buffer);

    /* Inicjalizuj bibliotekę kryptograficzną */
    if (cmox_initialize(NULL) != CMOX_INIT_SUCCESS)
        Error_Handler();

    /* 1. Szyfrowanie ramki za pomocą AES-CTR */
    printf("\n\r>> Szyfrowanie ramki danych <<\n\r");

    cipher_retval = cmox_cipher_encrypt(CMOX_AESFAST_CTR_ENC_ALGO,    /* Algorytm AES-CTR */
                               frame, frame_size,                      /* Ramka do zaszyfrowania */
                               aes_key, aes_key_size,                  /* Klucz AES */
                               iv, iv_size,                            /* Wektor inicjalizacyjny */
                               encrypted_frame, &computed_size);       /* Bufor na zaszyfrowane dane */

    /* Sprawdź czy szyfrowanie się powiodło */
    if (cipher_retval != CMOX_CIPHER_SUCCESS)
        Error_Handler();

    printf("Zaszyfrowana ramka (hex): ");
    btox(buffer, encrypted_frame, computed_size);
    printf("%s\n\r", buffer);

    /* 2. Obliczenie podpisu HMAC - używając osobnego klucza do HMAC */
    printf("\n\r>> Obliczanie podpisu HMAC <<\n\r");

    /* Użyj funkcji cmox_mac_compute z kluczem HMAC */
    mac_retval = cmox_mac_compute(CMOX_HMAC_SHA256_ALGO,            /* Algorytm HMAC-SHA256 */
                              encrypted_frame, computed_size,        /* Dane do podpisania */
                              hmac_key, hmac_key_size,               /* Klucz HMAC */
                              NULL, 0,                               /* Brak danych niestandardowych */
                              hmac, CMOX_SHA256_SIZE, &mac_size);    /* Bufor na podpis HMAC */

    /* Sprawdź czy obliczenie HMAC się powiodło */
    if (mac_retval != CMOX_MAC_SUCCESS)
        Error_Handler();

    printf("Podpis HMAC (hex): ");
    btox(buffer, hmac, mac_size);
    printf("%s\n\r", buffer);

    /* 3. Kompletna zaszyfrowana wiadomość do wysłania: [encrypted_frame | hmac] */
    printf("\n\r>> Przygotowanie kompletnej ramki danych <<\n\r");

    /* Skopiuj zaszyfrowaną ramkę */
    memcpy(output, encrypted_frame, computed_size);
    size_t output_frame_size = computed_size;

    /* Skopiuj podpis HMAC */
    memcpy(output + output_frame_size, hmac, mac_size);
    output_frame_size += mac_size;

    /* Ustaw rozmiar wyjściowy */
    *output_size = output_frame_size;

    printf("Kompletna ramka do wysyłki (hex): ");
    btox(buffer, output, output_frame_size);
    printf("%s\n\r", buffer);
    printf("Całkowity rozmiar ramki: %u bajtów\n\r", (unsigned int)output_frame_size);

    /* Zwolnij zasoby biblioteki kryptograficznej */
    if (cmox_finalize(NULL) != CMOX_INIT_SUCCESS)
        Error_Handler();
}
