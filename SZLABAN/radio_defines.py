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

# Constants for the radio module

from pyLoraRFM9x.constants import ModemConfig

# Board-specific configurations
SPI_PORT = 0            # SPI bus number (usually 0)
SPI_CHANNEL = 1         # SPI channel (0 for CE0, 1 for CE1)
INTERRUPT_PIN = 22      # GPIO pin connected to DIO0 (change according to your setup)
INTERRUPT_PIN1 = 23     # GPIO pin connected to DIO1
INTERRUPT_PIN2 = 24     # GPIO pin connected to DIO2
RESET_PIN = 25          # GPIO pin connected to reset (optional, if connected)


# FSK-specific configurations
FSK_FREQ = 868.2            # Frequency in MHz for FSK
FSK_TX_POWER = 0            # Transmission power in dBm for FSK
FSK_FIX_LEN = 0             # Set to 0 for variable length packets in FSK
FSK_PAYLOAD_LEN = 255       # Set maximum payload length for FSK

# LoRa-specific configurations
LORA_FREQ = 868.0           # Frequency in MHz for LoRa
LORA_MODEM_CONFIG = ModemConfig.Bw125Cr45Sf128 # Modem configuration for LoRa
LORA_SYNC_WORD = 0x12       # Sync word for LoRa (0x12 is default)
LORA_POWER = 0              # Transmission power in dBm for LoRa
LORA_ACKS = False           # Enable or disable ACKs for LoRa
LORA_ADDR = 2               # Device address for LoRa