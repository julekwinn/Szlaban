#include <string.h>
#include <stdbool.h> // Dodano dla typu bool
#include "board.h"
#include "radio.h"
#include "app_template.h"
#include "config.h"         // Dodaj to dla PILOT_ID, CRYPTO_*, itp.
#include "crypto_utils.h"   // Dodaj to dla create_secure_command_frame

#include "stm32u5xx_hal.h"

#define RF_FREQUENCY                                868200000 // Hz
#define TX_OUTPUT_POWER                             0         // dBm

#if defined( USE_MODEM_LORA )

#define LORA_BANDWIDTH                              0         // [0: 125 kHz,
                                                              //  1: 250 kHz,
                                                              //  2: 500 kHz,
                                                              //  3: Reserved]
#define LORA_SPREADING_FACTOR                       7         // [SF7..SF12]
#define LORA_CODINGRATE                             1         // [1: 4/5,
                                                              //  2: 4/6,
                                                              //  3: 4/7,
                                                              //  4: 4/8]
#define LORA_PREAMBLE_LENGTH                        8         // Same for Tx and Rx
#define LORA_SYMBOL_TIMEOUT                         5         // Symbols
#define LORA_FIX_LENGTH_PAYLOAD_ON                  false
#define LORA_IQ_INVERSION_ON                        false

#elif defined( USE_MODEM_FSK )

#define FSK_FDEV                                    25e3      // Hz
#define FSK_DATARATE                                50e3      // bps
#define FSK_BANDWIDTH                               50e3      // Hz
#define FSK_AFC_BANDWIDTH                           83.333e3  // Hz
#define FSK_PREAMBLE_LENGTH                         5         // Same for Tx and Rx
#define FSK_FIX_LENGTH_PAYLOAD_ON                   false

#else
    #error "Please define a modem in the compiler options."
#endif

typedef enum
{
    LOWPOWER,
    RX,
	RX_DONE,
    RX_TIMEOUT,
    RX_ERROR,
    TX,
    TX_TIMEOUT,
}States_t;

#define RX_TIMEOUT_VALUE                            1000
#define BUFFER_SIZE                                 50 // Zwiększono bufor dla dłuższych wiadomości i statusów

States_t State = LOWPOWER;

volatile int8_t RssiValue = 0;
volatile int8_t SnrValue = 0;


uint16_t BufferSize = BUFFER_SIZE;
uint8_t Buffer[BUFFER_SIZE];

typedef struct {
	int rxdone;
	int rxtimeout;
	int rxerror;
	int txdone;
	int txtimeout;
} trx_events_cnt_t;

trx_events_cnt_t trx_events_cnt;

int rx_cnt = 0;
int txdone_cnt = 0;

// --- NOWA FLAGA GLOBALNA ---
volatile bool transmission_complete = false;
volatile bool transmission_timed_out = false;

/*!
 * Radio events function pointer
 */
static RadioEvents_t RadioEvents;

/*!
 * \brief Function to be executed on Radio Tx Done event
 */
void OnTxDone( void );

/*!
 * \brief Function to be executed on Radio Rx Done event
 */
void OnRxDone( uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr );

/*!
 * \brief Function executed on Radio Tx Timeout event
 */
void OnTxTimeout( void );

/*!
 * \brief Function executed on Radio Rx Timeout event
 */
void OnRxTimeout( void );

/*!
 * \brief Function executed on Radio Rx Error event
 */
void OnRxError( void );

// Zmienna globalna do przechowywania licznika - powinna być zadeklarowana na zewnątrz funkcji
static uint8_t global_counter[8] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01};

/**
 * @brief Wysyła komendę "eszp_open" za pomocą funkcji szyfrującej oraz inkrementuje licznik
 * @return true jeśli transmisja zakończyła się sukcesem, false w przypadku błędu
 */
bool send_command(void)
{
    // Bufory na zaszyfrowaną ramkę
    uint8_t secure_frame[MAX_FRAME_SIZE];
    size_t secure_frame_size = 0;

    printf("Przygotowuję komendę eszp_open z licznikiem: %02X %02X %02X %02X %02X %02X %02X %02X\r\n",
           global_counter[0], global_counter[1], global_counter[2], global_counter[3],
           global_counter[4], global_counter[5], global_counter[6], global_counter[7]);

    // Utwórz bezpieczną ramkę z komendą "eszp_open"
    create_secure_command_frame(
        PILOT_ID,                                  // ID pilota z pliku config
        global_counter,                            // Licznik globalny
        CRYPTO_AES_KEY, sizeof(CRYPTO_AES_KEY),    // Klucz do szyfrowania AES
        CRYPTO_HMAC_KEY, sizeof(CRYPTO_HMAC_KEY),  // Klucz do podpisu HMAC
        CRYPTO_IV, sizeof(CRYPTO_IV),              // Wektor inicjalizacyjny
        secure_frame, &secure_frame_size);

    // Inkrementuj licznik dla kolejnego użycia
    // Prostą inkrementacja - zaczynając od najmniej znaczącego bajtu
    int i = 7;
    while (i >= 0) {
        global_counter[i]++;
        if (global_counter[i] != 0) break;  // Jeśli nie ma przepełnienia, zakończ
        i--;  // W przeciwnym wypadku kontynuuj inkrementację kolejnego bajtu
    }

    printf("Następna wartość licznika: %02X %02X %02X %02X %02X %02X %02X %02X\r\n",
           global_counter[0], global_counter[1], global_counter[2], global_counter[3],
           global_counter[4], global_counter[5], global_counter[6], global_counter[7]);

    // Wyślij przygotowaną ramkę jako surowe bajty
    printf("Rozpoczynam transmisję ramki o rozmiarze: %u bajtów\r\n", (unsigned)secure_frame_size);

    // Ustaw flagi transmisji
    transmission_complete = false;
    transmission_timed_out = false;
    State = TX;

    // Wyślij ramkę danych
    Radio.Send(secure_frame, secure_frame_size);

    // Czekaj na zakończenie transmisji
    printf("Czekam na zakończenie transmisji...\r\n");
    while (!transmission_complete && !transmission_timed_out)
    {
        DelayMs(10);
    }

    // Sprawdź status transmisji
    if (transmission_timed_out) {
        printf("Transmisja zakończona timeoutem.\r\n");
        return false;
    } else if (transmission_complete) {
        printf("Transmisja zakończona sukcesem (TX Done).\r\n");
        return true;
    } else {
        printf("Nieznany stan transmisji.\r\n");
        return false;
    }
}

// --- NOWA FUNKCJA DO WYSYŁANIA POJEDYNCZEJ WIADOMOŚCI ---
/**
 * @brief Sends a single radio message and waits for completion or timeout.
 * * @param message The null-terminated string to send.
 * @return true if transmission was successful (TxDone), false otherwise (Timeout).
 */
bool send_single_message(const char* message)
{
    uint8_t buf[BUFFER_SIZE];
    char freq_str[20];
    uint16_t message_len = strlen(message);


    if (message_len >= sizeof(buf)) {
        printf("Error: Message too long for buffer!\r\n");
        return false;
    }

    memset(buf, 0, sizeof(buf));
    strncpy((char*)buf, message, sizeof(buf));

    sprintf(freq_str, "%.3f MHz", RF_FREQUENCY / 1000000.0);

    printf("Preparing to send single message: %s\r\n", message);


    printf("Sending...\r\n");

    transmission_complete = false;
    transmission_timed_out = false;
    State = TX;

    Radio.Send(buf, message_len);

    printf("Waiting for TX completion or timeout...\r\n");
    while (!transmission_complete && !transmission_timed_out)
    {
        DelayMs(10);
    }

    if (transmission_timed_out) {
        printf("Transmission timed out.\r\n");
        DelayMs(2000);
        return false;
    } else if (transmission_complete) {
        printf("Transmission successful (TX Done).\r\n");
        return true;
    } else {
         return false;
    }
}


/** * Main application entry point.
 */
void app_main( void )
{
    bool tx_success;

    // Target board initialisation
    BoardInitMcu( );
    BoardInitPeriph( );

    // Radio initialization
    RadioEvents.TxDone = OnTxDone;
    RadioEvents.RxDone = OnRxDone;
    RadioEvents.TxTimeout = OnTxTimeout;
    RadioEvents.RxTimeout = OnRxTimeout;
    RadioEvents.RxError = OnRxError;

    Radio.Init( &RadioEvents );

    Radio.SetChannel( RF_FREQUENCY );

#if defined( USE_MODEM_LORA )

    Radio.SetTxConfig( MODEM_LORA, TX_OUTPUT_POWER, 0, LORA_BANDWIDTH,
                                   LORA_SPREADING_FACTOR, LORA_CODINGRATE,
                                   LORA_PREAMBLE_LENGTH, LORA_FIX_LENGTH_PAYLOAD_ON,
                                   true, 0, 0, LORA_IQ_INVERSION_ON, 3000 );

    // Konfiguracja RX nie jest ściśle potrzebna do samego wysyłania, ale może być ustawiona
    Radio.SetRxConfig( MODEM_LORA, LORA_BANDWIDTH, LORA_SPREADING_FACTOR,
                                   LORA_CODINGRATE, 0, LORA_PREAMBLE_LENGTH,
                                   LORA_SYMBOL_TIMEOUT, LORA_FIX_LENGTH_PAYLOAD_ON,
                                   0, true, 0, 0, LORA_IQ_INVERSION_ON, true );

#elif defined( USE_MODEM_FSK )

    Radio.SetTxConfig(  MODEM_FSK,						/* Radio modem to be used [0: FSK, 1: LoRa] */
    					TX_OUTPUT_POWER,				/* Sets the output power [dBm] */
						FSK_FDEV,						/* Sets the frequency deviation (FSK only) [Hz] */
						0,								/* Sets the bandwidth (LoRa only); 0 for FSK */
                        FSK_DATARATE, 					/* Sets the Datarate. FSK: 600..300000 bits/s */
						0,								/* Sets the coding rate (LoRa only) FSK: N/A ( set to 0 ) */
                        FSK_PREAMBLE_LENGTH,			/* Sets the preamble length. FSK: Number of bytes */
						FSK_FIX_LENGTH_PAYLOAD_ON,		/* Fixed length packets [0: variable, 1: fixed] */
						true,							/* Enables disables the CRC [0: OFF, 1: ON] */
						0,								/* Enables disables the intra-packet frequency hopping. FSK: N/A ( set to 0 ) */
						0,								/* Number of symbols bewteen each hop. FSK: N/A ( set to 0 ) */
						0,								/* Inverts IQ signals (LoRa only). FSK: N/A ( set to 0 ) */
						3000							/* Transmission timeout [ms] */
	);

    // Konfiguracja RX nie jest ściśle potrzebna do samego wysyłania
    Radio.SetRxConfig(  MODEM_FSK,						/* Radio modem to be used [0: FSK, 1: LoRa] */
    					FSK_BANDWIDTH,					/* Sets the bandwidth. FSK: >= 2600 and <= 250000 Hz. (CAUTION: This is "single side bandwidth") */
						FSK_DATARATE,					/* Sets the Datarate. FSK: 600..300000 bits/s */
						0,								/* Sets the coding rate (LoRa only) FSK: N/A ( set to 0 ) */
						FSK_AFC_BANDWIDTH,				/* Sets the AFC Bandwidth (FSK only). FSK: >= 2600 and <= 250000 Hz */
						FSK_PREAMBLE_LENGTH,			/* Sets the Preamble length. FSK: Number of bytes */
						0,								/* Sets the RxSingle timeout value (LoRa only). FSK: N/A ( set to 0 ) */
						FSK_FIX_LENGTH_PAYLOAD_ON,		/* Fixed length packets [0: variable, 1: fixed] */
						0,								/* Sets payload length when fixed lenght is used. */
						true,							/* Enables/Disables the CRC [0: OFF, 1: ON] */
                        0,								/* Enables disables the intra-packet frequency hopping. FSK: N/A ( set to 0 ) */
						0,								/* Number of symbols bewteen each hop. FSK: N/A ( set to 0 ) */
						false,							/* Inverts IQ signals (LoRa only). FSK: N/A ( set to 0 ) */
						false							/* Ustaw tryb ciągły na false, bo nie będziemy odbierać */
	);

#else
    #error "Please define a frequency band in the compiler options."
#endif

    tx_success = send_command();


    printf("Single transmission attempt finished. Result: %s\r\n", tx_success ? "Success" : "Fail/Timeout");

    Radio.Sleep();
    State = LOWPOWER;
    printf("Radio sleeping\r\n");
    DelayMs(100);
    printf("Back\r\n");

}

// --- Funkcja tx_loop NIE jest już potrzebna do głównego działania, ale zostawiam ją na wszelki wypadek ---
void tx_loop(void)
{

    printf("WARNING: tx_loop() called but should not be in single send mode.\r\n");
    while(1) { DelayMs(1000); } // Zablokuj, jeśli przypadkiem zostanie wywołana
}

void rx_loop(void)
{
    printf("WARNING: rx_loop() called but should not be in single send mode.\r\n");
}



void OnRxDone( uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr )
{
    BufferSize = size;
    memcpy( Buffer, payload, BufferSize );
    RssiValue = rssi;
    SnrValue = snr;
    State = RX_DONE;
    trx_events_cnt.rxdone++;
    printf("Callback: OnRxDone executed (unexpected in TX-only mode).\r\n");
}

void OnTxDone( void )
{
    printf(">>> OnTxDone ENTERED! <<<\r\n"); // Dodaj to
    State = LOWPOWER;
    trx_events_cnt.txdone++;
    transmission_complete = true;
    printf("Callback: OnTxDone executed.\r\n");
}

void OnTxTimeout( void )
{
    printf(">>> OnTxTimeout ENTERED! <<<\r\n"); // Dodaj to
    Radio.Sleep( );
    State = TX_TIMEOUT;
    trx_events_cnt.txtimeout++;
    transmission_timed_out = true;
    printf("Callback: OnTxTimeout executed.\r\n");
}

void OnRxTimeout( void )
{
    State = RX_TIMEOUT;
    trx_events_cnt.rxtimeout++;
    printf("Callback: OnRxTimeout executed (unexpected in TX-only mode).\r\n");
}

void OnRxError( void )
{
    State = RX_ERROR;
    trx_events_cnt.rxerror++;
    Radio.Rx(0);
    printf("Callback: OnRxError executed (unexpected in TX-only mode).\r\n");
}
