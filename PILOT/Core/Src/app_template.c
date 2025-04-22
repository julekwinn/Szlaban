
#include <stdio.h>
#include <string.h>
#include <stdbool.h>

#include "app_template.h"
#include "board.h"
#include "radio.h"
#include "config.h"
#include "crypto_utils.h"
#include "memory.h"

#include "stm32u5xx_hal.h"

/* Private defines -----------------------------------------------------------*/
#define RF_FREQUENCY                                868200000 // Hz - Dostosuj do swojego pasma
#define TX_OUTPUT_POWER                             0         // dBm - Dostosuj moc

// --- Konfiguracja LoRa ---
#if defined( USE_MODEM_LORA )
#define LORA_BANDWIDTH                              0         // [0: 125 kHz, 1: 250 kHz, 2: 500 kHz]
#define LORA_SPREADING_FACTOR                       7         // [SF7..SF12]
#define LORA_CODINGRATE                             1         // [1: 4/5, 2: 4/6, 3: 4/7, 4: 4/8]
#define LORA_PREAMBLE_LENGTH                        8         // Długość preambuły
#define LORA_SYMBOL_TIMEOUT                         5         // Timeout symboli LoRa
#define LORA_FIX_LENGTH_PAYLOAD_ON                  false     // Zmienna długość ramki
#define LORA_IQ_INVERSION_ON                        false     // Inwersja IQ wyłączona
#define LORA_TX_TIMEOUT_MS                          3000      // Timeout transmisji LoRa
// --- Konfiguracja FSK ---
#elif defined( USE_MODEM_FSK )
#define FSK_FDEV                                    25e3      // Hz - Dewiacja częstotliwości
#define FSK_DATARATE                                50e3      // bps - Przepływność
#define FSK_BANDWIDTH                               50e3      // Hz - Szerokość pasma (jednostronna)
#define FSK_AFC_BANDWIDTH                           83.333e3  // Hz - Szerokość pasma AFC
#define FSK_PREAMBLE_LENGTH                         5         // Długość preambuły (w bajtach)
#define FSK_FIX_LENGTH_PAYLOAD_ON                   false     // Zmienna długość ramki
#define FSK_TX_TIMEOUT_MS                           3000      // Timeout transmisji FSK
#else
    #error "Please define a modem (USE_MODEM_LORA or USE_MODEM_FSK) in compiler options."
#endif

#define RX_TIMEOUT_VALUE                            1000      // ms (nieużywane aktywnie w tym trybie)
#define BUFFER_SIZE                                 64        // Rozmiar bufora RX/TX


typedef enum
{
    APP_STATE_LOWPOWER,
    APP_STATE_TX,
    APP_STATE_TX_TIMEOUT,
    APP_STATE_RX,
    APP_STATE_RX_DONE,
    APP_STATE_RX_TIMEOUT,
    APP_STATE_RX_ERROR,
} AppStates_t;

typedef struct {
    int rxdone;
    int rxtimeout;
    int rxerror;
    int txdone;
    int txtimeout;
} RadioTrxEventsCounter_t;

static volatile AppStates_t AppState = APP_STATE_LOWPOWER;

static volatile int8_t LastRssiValue = 0;
static volatile int8_t LastSnrValue = 0;
static uint16_t RxDataBufferSize = BUFFER_SIZE;
static uint8_t RxDataBuffer[BUFFER_SIZE];

static RadioTrxEventsCounter_t RadioTrxEventsCounter;

static volatile bool TransmissionCompleteFlag = false;
static volatile bool TransmissionTimedOutFlag = false;
static volatile bool WriteCounterRequestFlag = false; // Flaga żądania zapisu licznika do EEPROM

static RadioEvents_t RadioEvents;


static uint8_t CurrentCounterValue[EEPROM_COUNTER_SIZE];

static void OnRadioTxDone( void );
static void OnRadioRxDone( uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr );
static void OnRadioTxTimeout( void );
static void OnRadioRxTimeout( void );
static void OnRadioRxError( void );

static void IncrementCounter(uint8_t* counter);
static bool SendCommandFrame(const uint8_t* counter_val);
static void ConfigureRadio();


void app_main( void )
{
    bool tx_initiated = false;
    uint8_t init_flag;
    bool initialization_needed = false;

    printf("\r\n===== app_main START =====\r\n");

    if (!Memory_Init()) {
        printf("app_main: KRYTYCZNY BŁĄD inicjalizacji pamięci EEPROM!\r\n");
        Error_Handler();
        return;
    }

    if (Memory_ReadInitFlag(&init_flag)) {
        if (init_flag != EEPROM_INIT_FLAG_VALUE) {
            printf("app_main: Flaga inicjalizacji niepoprawna (0x%02X != 0x%02X). EEPROM wymaga inicjalizacji.\r\n",
                   init_flag, EEPROM_INIT_FLAG_VALUE);
            initialization_needed = true;
        } else {
            printf("app_main: Flaga inicjalizacji poprawna (0x%02X). EEPROM zainicjalizowany.\r\n", init_flag);
            initialization_needed = false;
        }
    } else {
        printf("app_main: BŁĄD odczytu flagi inicjalizacji! Zakładam, że EEPROM wymaga inicjalizacji.\r\n");
        initialization_needed = true;
    }

    if (initialization_needed) {
        printf("app_main: Inicjalizuję licznik wartością 1 i zapisuję do EEPROM...\r\n");
        memset(CurrentCounterValue, 0, EEPROM_COUNTER_SIZE);
        CurrentCounterValue[EEPROM_COUNTER_SIZE - 1] = 1; // Ustaw ostatni bajt na 1

        if (Memory_WriteCounter(CurrentCounterValue)) {
            if (!Memory_WriteInitFlag(EEPROM_INIT_FLAG_VALUE)) {
                printf("app_main: KRYTYCZNY BŁĄD zapisu flagi inicjalizacji!\r\n");
            } else {
                 printf("app_main: Inicjalizacja EEPROM zakończona.\r\n");
            }
        } else {
             printf("app_main: KRYTYCZNY BŁĄD zapisu początkowego licznika!\r\n");
             Error_Handler();
             return;
        }
    } else {
        printf("app_main: Odczytuję licznik z zainicjalizowanego EEPROM...\r\n");
        if (!Memory_ReadCounter(CurrentCounterValue)) {
            printf("app_main: BŁĄD odczytu licznika z zainicjalizowanego EEPROM! Używam wartości awaryjnej (1).\r\n");
            memset(CurrentCounterValue, 0, EEPROM_COUNTER_SIZE);
            CurrentCounterValue[EEPROM_COUNTER_SIZE - 1] = 1;

        }
    }

    BoardInitMcu();
    BoardInitPeriph();

    RadioEvents.TxDone = OnRadioTxDone;
    RadioEvents.RxDone = OnRadioRxDone;
    RadioEvents.TxTimeout = OnRadioTxTimeout;
    RadioEvents.RxTimeout = OnRadioRxTimeout;
    RadioEvents.RxError = OnRadioRxError;

    Radio.Init(&RadioEvents);

    ConfigureRadio();

    tx_initiated = SendCommandFrame(CurrentCounterValue);

    if (tx_initiated)
    {
        printf("app_main: Transmisja zainicjowana. Oczekiwanie na wynik...\r\n");
        AppState = APP_STATE_TX;
        while (!TransmissionCompleteFlag && !TransmissionTimedOutFlag)
        {
             HAL_Delay(5);
        }

        if (TransmissionTimedOutFlag) {
            printf("app_main: Transmisja zakończona TIMEOUTEM.\r\n");
            AppState = APP_STATE_TX_TIMEOUT;
        } else if (TransmissionCompleteFlag) {
            printf("app_main: Transmisja zakończona SUKCESEM (TX Done).\r\n");
            WriteCounterRequestFlag = true;
            AppState = APP_STATE_LOWPOWER;
        } else {
            printf("app_main: BŁĄD - Nieznany stan po oczekiwaniu na transmisję.\r\n");
            AppState = APP_STATE_LOWPOWER;
        }
    }
    else
    {
        printf("app_main: BŁĄD inicjalizacji transmisji (SendCommandFrame nie powiódł się).\r\n");
        AppState = APP_STATE_LOWPOWER;
    }

    if (WriteCounterRequestFlag)
    {
        printf("app_main: Inkrementacja i zapis licznika do EEPROM...\r\n");
        IncrementCounter(CurrentCounterValue);

        if (Memory_WriteCounter(CurrentCounterValue)) {
             printf("app_main: Nowy licznik zapisany pomyślnie.\r\n");
        } else {
             printf("app_main: KRYTYCZNY BŁĄD zapisu licznika do EEPROM po udanej transmisji!\r\n");
        }
        WriteCounterRequestFlag = false;
    }

    printf("app_main: Uśpienie radia...\r\n");
    Radio.Sleep();
    AppState = APP_STATE_LOWPOWER;
    printf("===== app_main KONIEC =====\r\n\r\n");
}


static void ConfigureRadio()
{
    Radio.SetChannel( RF_FREQUENCY );

#if defined( USE_MODEM_LORA )
    printf("Konfiguracja radia: LoRa\r\n");
    Radio.SetTxConfig( MODEM_LORA, TX_OUTPUT_POWER, 0, LORA_BANDWIDTH,
                                   LORA_SPREADING_FACTOR, LORA_CODINGRATE,
                                   LORA_PREAMBLE_LENGTH, LORA_FIX_LENGTH_PAYLOAD_ON,
                                   true, 0, 0, LORA_IQ_INVERSION_ON, LORA_TX_TIMEOUT_MS );

    Radio.SetRxConfig( MODEM_LORA, LORA_BANDWIDTH, LORA_SPREADING_FACTOR,
                                   LORA_CODINGRATE, 0, LORA_PREAMBLE_LENGTH,
                                   LORA_SYMBOL_TIMEOUT, LORA_FIX_LENGTH_PAYLOAD_ON,
                                   0, true, 0, 0, LORA_IQ_INVERSION_ON, true );

#elif defined( USE_MODEM_FSK )
    printf("Konfiguracja radia: FSK\r\n");
    Radio.SetTxConfig( MODEM_FSK, TX_OUTPUT_POWER, FSK_FDEV, 0, FSK_DATARATE, 0,
                       FSK_PREAMBLE_LENGTH, FSK_FIX_LENGTH_PAYLOAD_ON, true, 0, 0, 0, FSK_TX_TIMEOUT_MS );

    // Konfiguracja RX (opcjonalna dla trybu TX-only)
    Radio.SetRxConfig( MODEM_FSK, FSK_BANDWIDTH, FSK_DATARATE, 0, FSK_AFC_BANDWIDTH,
                       FSK_PREAMBLE_LENGTH, 0, FSK_FIX_LENGTH_PAYLOAD_ON, 0, true, 0, 0, false, false );
#endif
}


static void IncrementCounter(uint8_t* counter) {
    int i = EEPROM_COUNTER_SIZE - 1;
    while (i >= 0) {
        counter[i]++;
        if (counter[i] != 0) {
            break;
        }
        i--;
    }
}


static bool SendCommandFrame(const uint8_t* counter_val)
{
    uint8_t secure_frame[MAX_FRAME_SIZE];
    size_t secure_frame_size = 0; // Inicjalizuj rozmiarem 0

    printf("SendCommandFrame: Tworzenie ramki z licznikiem: %02X %02X %02X %02X %02X %02X %02X %02X\r\n",
           counter_val[0], counter_val[1], counter_val[2], counter_val[3],
           counter_val[4], counter_val[5], counter_val[6], counter_val[7]);

    create_secure_command_frame(
            PILOT_ID,                                // ID urządzenia
            counter_val,                             // Aktualna wartość licznika
            CRYPTO_AES_KEY, sizeof(CRYPTO_AES_KEY),  // Klucz AES
            CRYPTO_HMAC_KEY, sizeof(CRYPTO_HMAC_KEY),// Klucz HMAC
            CRYPTO_IV, sizeof(CRYPTO_IV),            // Wektor inicjalizacyjny IV
            secure_frame, &secure_frame_size);       // Bufor wyjściowy i wskaźnik na rozmiar

    if (secure_frame_size == 0)
    {
         printf("SendCommandFrame: KRYTYCZNY BŁĄD tworzenia bezpiecznej ramki (rozmiar 0)!\r\n");
         return false; // Zwróć błąd
    }

    if (secure_frame_size > BUFFER_SIZE) {
         printf("SendCommandFrame: BŁĄD - Wygenerowana ramka (%u B) jest za duża dla bufora radia (%d B)!\r\n",
                (unsigned)secure_frame_size, BUFFER_SIZE);
         return false;
    }

    printf("SendCommandFrame: Rozpoczynam transmisję radiową ramki (%u bajtów)...\r\n", (unsigned)secure_frame_size);

    TransmissionCompleteFlag = false;
    TransmissionTimedOutFlag = false;
    WriteCounterRequestFlag = false;

    Radio.Send(secure_frame, secure_frame_size);


    return true;
}


static void OnRadioTxDone( void )
{
    printf("Callback: OnRadioTxDone!\r\n");
    RadioTrxEventsCounter.txdone++;
    TransmissionCompleteFlag = true;  // Ustaw flagę sukcesu
    TransmissionTimedOutFlag = false; // Upewnij się, że flaga timeout jest skasowana
}
static void OnRadioTxTimeout( void )
{
    printf("Callback: OnRadioTxTimeout!\r\n");

    Radio.Sleep();
    RadioTrxEventsCounter.txtimeout++;
    TransmissionTimedOutFlag = true;  // Ustaw flagę timeoutu
    TransmissionCompleteFlag = false; // Upewnij się, że flaga sukcesu jest skasowana
}
static void OnRadioRxDone( uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr )
{
    printf("Callback: OnRadioRxDone (Odebrano %u bajtów, RSSI:%d, SNR:%d) - Niespodziewane.\r\n", size, rssi, snr);
    if (size > 0 && size <= BUFFER_SIZE) {
        memcpy( RxDataBuffer, payload, size );
        RxDataBufferSize = size;
    } else {
        RxDataBufferSize = 0;
    }
    LastRssiValue = rssi;
    LastSnrValue = snr;
    AppState = APP_STATE_RX_DONE;
    RadioTrxEventsCounter.rxdone++;

}


static void OnRadioRxTimeout( void )
{
    printf("Callback: OnRadioRxTimeout - Niespodziewane.\r\n");
    AppState = APP_STATE_RX_TIMEOUT;
    RadioTrxEventsCounter.rxtimeout++;

}


static void OnRadioRxError( void )
{
    printf("Callback: OnRadioRxError - Niespodziewane.\r\n");
    AppState = APP_STATE_RX_ERROR;
    RadioTrxEventsCounter.rxerror++;

}


void tx_loop(void)
{
    printf("WARNING: tx_loop() jest przestarzała w tym trybie.\r\n");
    while(1) { HAL_Delay(1000); }
}


void rx_loop(void)
{
    printf("WARNING: rx_loop() nie jest używana w tym trybie.\r\n");

    while(1) {
        HAL_Delay(100);
    }
}


bool send_single_message(const char* message)
{
    uint16_t message_len = strlen(message);
    printf("WARNING: send_single_message() nie jest używana dla szyfrowanych komend.\r\n");

    if (message_len >= BUFFER_SIZE) {
        printf("send_single_message: Error - Wiadomość za długa!\r\n");
        return false;
    }

    printf("send_single_message: Wysyłanie '%s'...\r\n", message);

    TransmissionCompleteFlag = false;
    TransmissionTimedOutFlag = false;
    AppState = APP_STATE_TX;

    Radio.Send((uint8_t*)message, message_len);

    while (!TransmissionCompleteFlag && !TransmissionTimedOutFlag) {
        HAL_Delay(10);
    }

    if (TransmissionTimedOutFlag) {
        printf("send_single_message: Timeout transmisji.\r\n");
        Radio.Sleep();
        return false;
    } else if (TransmissionCompleteFlag) {
        printf("send_single_message: Transmisja OK (TX Done).\r\n");
        Radio.Sleep(); // Uśpij po wysłaniu
        return true;
    } else {
        printf("send_single_message: Nieznany stan po transmisji.\r\n");
        Radio.Sleep();
        return false;
    }
}

