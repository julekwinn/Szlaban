# radio_handle.py
# -*- coding: utf-8 -*-

"""""
MIT License

Copyright (c) 2024 BEER-TEAM (Piotr Polnau, Jan Sosulski, Piotr Baprawski)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

# Standardowe importy
import RPi.GPIO as GPIO
import radio_defines # Załóżmy, że ten plik istnieje i zawiera definicje
from enum import Enum, auto
from time import sleep
from threading import Thread

# Importy bibliotek radiowych
try:
    from pyLoraRFM9x import LoRa, ModemConfig
except ImportError:
    print("OSTRZEŻENIE: Nie można zaimportować pyLoraRFM9x. Tryb LoRa nie będzie działał.")
    LoRa = None # Ustaw na None, aby uniknąć błędów przy inicjalizacji

try:
    from sx_1276_driver.radio_driver import FSK
except ImportError:
    print("OSTRZEŻENIE: Nie można zaimportować sx_1276_driver. Tryb FSK nie będzie działał.")
    FSK = None # Ustaw na None


class RadioMode(Enum):
    """
    Enum class for Radio Modes: FSK and LoRa.

    Possible values:

    FSK: Frequency Shift Keying

    LORA: LoRa
    """
    FSK = auto()  # Frequency Shift Keying
    LORA = auto()  # LoRa

    def __str__(self) -> str:
        return self.name

class RadioHandler:
    def __init__(self, mode, data_callback):
        """
        Initialize the RadioHandler class with SPI, GPIO setup, and set the receive mode.

        :param mode: RadioMode.FSK for Frequency Shift Keying, RadioMode.LORA for LoRa.
        :param data_callback: Callback function to handle received data (expects bytes).
        """
        GPIO.setmode(GPIO.BCM)  # Use BCM GPIO numbering
        self.mode = mode
        self.data_callback = data_callback  # Store the callback function
        self.fsk_handler = None
        self.lora_handler = None

        if self.mode == RadioMode.FSK:
            if FSK is None:
                raise ImportError("Nie można zainicjalizować FSK, brak biblioteki sx_1276_driver.")
            # Initialize FSK transceiver
            self.fsk_handler = FSK(
                spiport=radio_defines.SPI_PORT,
                channel=radio_defines.SPI_CHANNEL,
                interrupt=radio_defines.INTERRUPT_PIN,
                interrupt1=radio_defines.INTERRUPT_PIN1,
                interrupt2=radio_defines.INTERRUPT_PIN2,
                reset_pin=radio_defines.RESET_PIN,
                freq=radio_defines.FSK_FREQ,
                tx_power=radio_defines.FSK_TX_POWER,
                fixLEN=radio_defines.FSK_FIX_LEN,
                payload_len=radio_defines.FSK_PAYLOAD_LEN
            )
            self.fsk_handler.on_recv = self.handle_received_data # Ustawienie callbacku
            self.fsk_handler.SX1276SetRx_fsk()  # Start receiving in FSK mode
            print(f"{self.mode} handler is running... Waiting for data.")

        elif self.mode == RadioMode.LORA:
            if LoRa is None:
                 raise ImportError("Nie można zainicjalizować LoRa, brak biblioteki pyLoraRFM9x.")
            # Initialize LoRa transceiver using macros from radio_defines and set acks to False
            self.lora_handler = LoRa(
                spi_channel=radio_defines.SPI_CHANNEL,
                interrupt_pin=radio_defines.INTERRUPT_PIN,
                my_address=radio_defines.LORA_ADDR,
                spi_port=radio_defines.SPI_PORT,
                reset_pin=radio_defines.RESET_PIN,
                freq=radio_defines.LORA_FREQ,
                tx_power=radio_defines.LORA_POWER,
                modem_config=radio_defines.LORA_MODEM_CONFIG,
                acks=radio_defines.LORA_ACKS,
                receive_all=True
            )

            self.lora_handler.on_recv = self.handle_received_data  # Set callback for received data
            self.lora_handler.set_mode_rx()  # Start in receive mode
            print(f"{self.mode} handler is running... Waiting for data.")

        else:
            raise ValueError("Invalid mode. Please choose RadioMode.FSK or RadioMode.LORA.")


    def start_rx(self):
        """Start receiving data in FSK or LoRa mode."""
        if self.mode == RadioMode.FSK and self.fsk_handler:
            self.fsk_handler.SX1276SetRx_fsk()
        elif self.mode == RadioMode.LORA and self.lora_handler:
            self.lora_handler.set_mode_rx()  # Set LoRa to RX mode
        else:
             print(f"Handler for mode {self.mode} not initialized, cannot start RX.")
             # Można rozważyć rzucenie wyjątku, jeśli jest to błąd krytyczny
             # raise RuntimeError(f"Handler for mode {self.mode} not initialized.")

    def handle_received_data(self, data, rssi=None, index=None):
        """
        Handle received data for both FSK and LoRa.
        Passes the RAW data (bytes) to the callback.

        :param data: The received data payload (expected as bytes or iterable of byte ints).
        """
        if self.mode == RadioMode.FSK:
            # FSK Mode: Data received through the FSK driver
            if data:
                # --- POPRAWKA: Przekaż 'data' jako bytes, konwertując jeśli trzeba ---
                print(f"Received FSK data (Typ: {type(data)}, RSSI: {rssi} dBm, Index: {index})")

                data_bytes = None
                # Sprawdź, czy dane to lista/krotka liczb (częsty przypadek w bibliotekach C)
                if isinstance(data, (list, tuple)):
                    try:
                        # Spróbuj skonwertować listę/krotkę intów na bytes
                        data_bytes = bytes(data)
                        #print(f"FSK data converted to bytes (len: {len(data_bytes)}): {data_bytes!r}")
                    except (ValueError, TypeError) as e:
                        print(f"ERROR: Błąd konwersji listy/krotki FSK na bajty: {e}")
                # Sprawdź, czy dane to już bajty
                elif isinstance(data, bytes):
                     data_bytes = data # Już jest w poprawnym formacie
                     print(f"FSK data is already bytes (len: {len(data_bytes)}): {data_bytes!r}")
                else:
                    # Nieznany lub nieobsługiwany typ danych
                    print(f"ERROR: Otrzymano nieoczekiwany typ danych z FSK driver: {type(data)}")

                # Wywołaj callback tylko jeśli mamy poprawne bajty
                if data_bytes is not None and self.data_callback:
                    try:
                        self.data_callback(data_bytes, rssi, index) # Przekaż obiekt bytes
                    except Exception as e:
                        print(f"ERROR: Błąd podczas wywoływania data_callback dla FSK: {e}")
                elif data_bytes is None:
                    print("FSK Callback not called due to data conversion error or invalid type.")

            else:
                print("Received empty or noise FSK data.")

        elif self.mode == RadioMode.LORA:
            # LoRa Mode: Data received through the LoRa transceiver (obiekt 'data' z pyLoraRFM9x)
            # Załóżmy, że data.message zawiera payload jako bytes
            payload_bytes = None
            lora_rssi = getattr(data, 'rssi', None) # Bezpieczne pobranie RSSI

            if data and hasattr(data, 'message'):
                 if isinstance(data.message, bytes):
                     payload_bytes = data.message
                     print(f"Received LoRa data (Payload len: {len(payload_bytes)}, RSSI: {lora_rssi} dBm): {payload_bytes!r}")
                 elif isinstance(data.message, (list, tuple)): # Na wszelki wypadek, gdyby zwracało listę intów
                      try:
                          payload_bytes = bytes(data.message)
                          print(f"LoRa data payload converted to bytes (len: {len(payload_bytes)}, RSSI: {lora_rssi} dBm): {payload_bytes!r}")
                      except (ValueError, TypeError) as e:
                           print(f"ERROR: Błąd konwersji payloadu LoRa (lista/krotka) na bajty: {e}")
                 else:
                     print(f"ERROR: Otrzymano nieoczekiwany typ payloadu LoRa: {type(data.message)}")
            else:
                 print(f"Received invalid or empty LoRa data object (Type: {type(data)})")

            # Wywołaj callback tylko jeśli mamy poprawne bajty payloadu
            if payload_bytes is not None and self.data_callback:
                 try:
                    # Przekazujemy tylko payload i rssi, bo LoRa nie ma 'index'
                    self.data_callback(payload_bytes, lora_rssi)
                 except Exception as e:
                        print(f"ERROR: Błąd podczas wywoływania data_callback dla LoRa: {e}")
            elif payload_bytes is None:
                 print("LoRa Callback not called due to missing/invalid payload.")


    def send(self, message):
        """Send a message in FSK or LoRa mode."""
        if self.mode == RadioMode.FSK:
            self._send_fsk(message)
        elif self.mode == RadioMode.LORA:
            self._send_lora(message)
        sleep(0.1) # Krótka pauza po wysłaniu
        self.start_rx()  # Wróć do trybu odbioru po wysłaniu

    def _send_fsk(self, message):
        """Send a message using FSK mode."""
        if self.fsk_handler:
            print(f"Sending FSK message: {message}") # Uwaga: jeśli message to bytes, print może nie być czytelny
            # Upewnij się, że fsk_handler.send_fsk oczekuje odpowiedniego typu (bytes/str?)
            # Jeśli oczekuje str, a message jest bytes, trzeba by zakodować: message.encode(...)
            # Jeśli oczekuje bytes, a message jest str, trzeba by zakodować: message.encode(...)
            # Jeśli oczekuje listę intów, a message jest bytes: list(message)
            # Sprawdź dokumentację/kod sx_1276_driver! Załóżmy, że oczekuje bytes lub str.
            if isinstance(message, str):
                data_to_send = message.encode('utf-8', errors='ignore') # Przykład kodowania
            elif isinstance(message, bytes):
                data_to_send = message
            else:
                print("ERROR: Nieobsługiwany typ wiadomości do wysłania przez FSK.")
                return
            try:
                self.fsk_handler.send_fsk(data_to_send)
            except Exception as e:
                print(f"ERROR: Błąd podczas wysyłania FSK: {e}")
        else:
             print("ERROR: FSK handler not initialized, cannot send.")

    def _send_lora(self, message):
        """Send a message using LoRa mode."""
        if self.lora_handler:
            print(f"Sending LoRa message: {message}") # Podobnie, print może nie być idealny dla bytes
            # Biblioteka pyLoraRFM9x.send oczekuje bytes lub str (który zakoduje jako utf-8)
            # Załóżmy, że chcemy wysłać jako bytes, jeśli to możliwe
            if isinstance(message, str):
                data_to_send = message.encode('utf-8', errors='ignore')
            elif isinstance(message, bytes):
                data_to_send = message
            else:
                 print("ERROR: Nieobsługiwany typ wiadomości do wysłania przez LoRa.")
                 return
            try:
                # Drugi argument to adres odbiorcy (destination address)
                # Użyjmy jakiegoś zdefiniowanego adresu lub broadcast (jeśli biblioteka wspiera)
                destination_address = radio_defines.LORA_DEFAULT_DEST_ADDR # Załóżmy, że istnieje w defines
                self.lora_handler.send(data_to_send, destination_address)
            except Exception as e:
                 print(f"ERROR: Błąd podczas wysyłania LoRa: {e}")
        else:
            print("ERROR: LoRa handler not initialized, cannot send.")

    def cleanup(self):
        """Clean up resources for FSK or LoRa."""
        print("Cleaning up Radio Handler...")
        if self.fsk_handler:
            try:
                self.fsk_handler.close()
                print("FSK handler closed.")
            except Exception as e:
                print(f"ERROR during FSK handler cleanup: {e}")
        if self.lora_handler:
            try:
                self.lora_handler.close()
                print("LoRa handler closed.")
            except Exception as e:
                 print(f"ERROR during LoRa handler cleanup: {e}")
        # GPIO cleanup jest zwykle robione na końcu głównego skryptu,
        # aby inne komponenty mogły z niego korzystać.
        # Można dodać tutaj, jeśli RadioHandler jest jedynym użytkownikiem GPIO.
        # GPIO.cleanup()
        print("Radio Handler cleanup finished.")