import time
from enum import Enum
import math
from collections import namedtuple
from random import random

import RPi.GPIO as GPIO
import spidev

import threading

from sx_1276_driver.defines import *

class FSK(object):
    def __init__(self, spiport, channel, interrupt,interrupt1, interrupt2, reset_pin=None, freq=860, tx_power=0, crypto=None, fixLEN=0, payload_len=0):
        """
        Lora((spiport, channel, interrupt, this_address, freq=915, tx_power=14,
                 modem_config=ModemConfig.Bw125Cr45Sf128, receive_all=False,
                 acks=False, crypto=None, reset_pin=False)
        spiport: spi port connected to module, 1 or 0
        channel: SPI channel [0 for CE0, 1 for CE1]
        interrupt: Raspberry Pi interrupt pin (BCM)
        this_address: set address for this device [0-254]
        reset_pin: the Raspberry Pi port used to reset the RFM9x if connected
        freq: frequency in MHz
        tx_power: transmit power in dBm
        modem_config: Check ModemConfig. Default is compatible with the Radiohead library
        receive_all: if True, don't filter packets on address
        acks: if True, request acknowledgments
        crypto: if desired, an instance of pycrypto AES
        """


        self._spiport = spiport
        self._channel = channel
        self._interrupt = interrupt
        self._interrupt1 = interrupt1
        self._interrupt2 = interrupt2
        self._hw_lock = threading.RLock() # lock for multithreaded access

        self._mode = MODE_SLEEP
        self._freq = freq
        self._tx_power = tx_power

        self.fixLEN = fixLEN
        self.payload_len = payload_len
        self.crypto = crypto
        self.wait_packet_sent_timeout = 1

        self._rx_buffer = []
        self._rx_payload_len = 0
        self._rssi = 0
        self._received_msg_index = 0

        # Setup the module
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._interrupt, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(self._interrupt1, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(self._interrupt2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.add_event_detect(self._interrupt, GPIO.RISING, callback=self._handle_interrupt)
        GPIO.add_event_detect(self._interrupt1, GPIO.RISING, callback=self._handle_interrupt1)
        GPIO.add_event_detect(self._interrupt2, GPIO.RISING, callback=self._handle_interrupt2)

        # reset the board
        if reset_pin:
            GPIO.setup(reset_pin,GPIO.OUT)
            GPIO.output(reset_pin,GPIO.LOW)
            time.sleep(0.01)
            GPIO.output(reset_pin,GPIO.HIGH)
            time.sleep(0.01)


        self.spi = spidev.SpiDev()
        self.spi.open(spiport, self._channel)
        self.spi.max_speed_hz = 5000000

        self.SX1276Init()

        self.SX1276SetChannel()

        self.SX1276SetTxConfig(fixLEN = self.fixLEN)

        self.SX1276SetRxConfig(fixLEN = self.fixLEN, payload_len = self.payload_len)



    def SX1276Init(self):
        #SX1276Init start
        self.SX1276SetModem()
        self._spi_write(REG_FSK_LNA, REG_FSK_LNA_INIT_VAL)

        self.SX1276SetModem()
        self._spi_write(REG_FSK_RXCONFIG, REG_FSK_RXCONFIG_INIT_VAL)

        self.SX1276SetModem()
        self._spi_write(REG_FSK_RSSICONFIG, REG_FSK_RSSICONFIG_INIT_VAL)

        self.SX1276SetModem()
        self._spi_write(REG_FSK_AFCFEI, REG_FSK_AFCFEI_INIT_VAL)

        self.SX1276SetModem()
        self._spi_write(REG_FSK_PREAMBLEDETECT, REG_FSK_PREAMBLEDETECT_INIT_VAL)
        
        self.SX1276SetModem()
        self._spi_write(REG_FSK_OSC, REG_FSK_OSC_INIT_VAL)

        self.SX1276SetModem()
        self._spi_write(REG_FSK_SYNCCONFIG, REG_FSK_SYNCCONFIG_INIT_VAL)

        self.SX1276SetModem()
        self._spi_write(REG_FSK_SYNCVALUE1, REG_FSK_SYNCVALUE1_INIT_VAL)

        self.SX1276SetModem()
        self._spi_write(REG_FSK_SYNCVALUE2, REG_FSK_SYNCVALUE2_INIT_VAL)

        self.SX1276SetModem()
        self._spi_write(REG_FSK_SYNCVALUE3, REG_FSK_SYNCVALUE3_INIT_VAL)

        self.SX1276SetModem()
        self._spi_write(REG_FSK_PACKETCONFIG1, REG_FSK_PACKETCONFIG1_INIT_VAL)

        self.SX1276SetModem()
        self._spi_write(REG_FSK_FIFOTHRESH, REG_FSK_FIFOTHRESH_INIT_VAL)

        self.SX1276SetModem()
        self._spi_write(REG_FSK_IMAGECAL, REG_FSK_IMAGECAL_INIT_VAL)

        self.SX1276SetModem()
        self._spi_write(REG_FSK_DIOMAPPING1, REG_FSK_DIOMAPPING1_INIT_VAL)

        self.SX1276SetModem()
        self._spi_write(REG_FSK_DIOMAPPING2, REG_FSK_DIOMAPPING2_INIT_VAL)

        self.SX1276SetModem()

        #SX1276Init end

    def SX1276SetChannel(self):
        # # set frequency
        frf = int((self._freq * 1000000.0) / FREQ_STEP)
        self._spi_write(REG_06_FRF_MSB, (frf >> 16) & 0xff)
        self._spi_write(REG_07_FRF_MID, (frf >> 8) & 0xff)
        self._spi_write(REG_08_FRF_LSB, frf & 0xff)

    def SX1276SetModem(self):
        # SX1276SetModem() start

        # SX1276SetOpMode(RF_OPMODE_SLEEP) start
        temp = (self._spi_read(REG_01_OP_MODE) & RF_OPMODE_MASK )
        self._spi_write(REG_01_OP_MODE, temp | MODE_SLEEP)
        # SX1276SetOpMode(RF_OPMODE_SLEEP) stop

        temp = (self._spi_read(REG_01_OP_MODE) & RFLR_OPMODE_LONGRANGEMODE_MASK)
        self._spi_write(REG_01_OP_MODE, temp | LONG_RANGE_MODE_OFF)


        self._spi_write(REG_40_DIO_MAPPING1, 0x00)
        self._spi_write(REG_41_DIO_MAPPING2, 0x30)

        # SX1276SetModem() stop

    def SX1276SetTxConfig(self, fixLEN):
        self.SX1276SetModem()

        # Set tx power
        if self._tx_power < 5:
            self._tx_power = 5
        if self._tx_power > 23:
            self._tx_power = 23

        if self._tx_power > 20:
            self._spi_write(REG_4D_PA_DAC, PA_DAC_ENABLE)
            self._tx_power -= 3
        else:
            self._spi_write(REG_4D_PA_DAC, PA_DAC_DISABLE)

        self._spi_write(REG_09_PA_CONFIG, PA_SELECT | (self._tx_power - 5))
        # self._spi_write(REG_09_PA_CONFIG, 240)

        # self._spi_write(REG_4D_PA_DAC, 132)

        # print(f"REG_PACONFIG - {self._spi_read(REG_09_PA_CONFIG)}")

        # print(f"REG_PADAC - {self._spi_read(REG_4D_PA_DAC)}")
        # Set tx power end

        fdev = int((float(FSK_FDEV) / float(FREQ_STEP)))

        self._spi_write(REG_FDEVMSB, (fdev >> 8) & 0xff)
        # print(f"{REG_FDEVMSB} - {self._spi_read(REG_FDEVMSB)}")
        self._spi_write(REG_FDEVLSB, fdev & 0xff)
        # print(f"{REG_FDEVLSB} - {self._spi_read(REG_FDEVLSB)}")

        datarate = int((float(XTAL_FREQ) / float(FSK_DATARATE)))
        self._spi_write(REG_BITRATEMSB, (datarate >> 8) & 0xff)
        # print(f"{REG_BITRATEMSB} - {self._spi_read(REG_BITRATEMSB)}")
        self._spi_write(REG_BITRATELSB, datarate & 0xff)
        # print(f"{REG_BITRATELSB} - {self._spi_read(REG_BITRATELSB)}")

        self._spi_write(REG_PREAMBLEMSB, (FSK_PREAMBLE_LENGTH >> 8) & 0xff)
        # print(f"{REG_PREAMBLEMSB} - {self._spi_read(REG_PREAMBLEMSB)}")
        self._spi_write(REG_PREAMBLELSB, FSK_PREAMBLE_LENGTH & 0xff)
        # print(f"{REG_PREAMBLELSB} - {self._spi_read(REG_PREAMBLELSB)}")

        if fixLEN == 0:
            self._spi_write(REG_PACKETCONFIG1, (self._spi_read(REG_PACKETCONFIG1) & RF_PACKETCONFIG1_CRC_MASK &
                            RF_PACKETCONFIG1_PACKETFORMAT_MASK) | RF_PACKETCONFIG1_PACKETFORMAT_VARIABLE | (FSK_CRC_ON << 4))
        else:
            self._spi_write(REG_PACKETCONFIG1, (self._spi_read(REG_PACKETCONFIG1) & RF_PACKETCONFIG1_CRC_MASK &
                            RF_PACKETCONFIG1_PACKETFORMAT_MASK) | RF_PACKETCONFIG1_PACKETFORMAT_FIXED | (FSK_CRC_ON << 4))
        # print(f"{REG_PACKETCONFIG1} - {self._spi_read(REG_PACKETCONFIG1)}")

    def SX1276SetRxConfig(self, fixLEN, payload_len):
        self.SX1276SetModem()
        
        datarate = int((float(XTAL_FREQ) / float(FSK_DATARATE))) % 65536
        self._spi_write(REG_BITRATEMSB, (datarate >> 8) & 0xff)
        self._spi_write(REG_BITRATELSB, datarate & 0xff)

        self._spi_write(REG_RXBW, self.GetFSkBandwidthRegValue(FSK_BANDWIDTH))
        self._spi_write(REG_AFCBW, self.GetFSkBandwidthRegValue(FSK_AFC_BANDWIDTH))

        self._spi_write(REG_PREAMBLEMSB, (FSK_PREAMBLE_LENGTH >> 8) & 0xff)
        self._spi_write(REG_PREAMBLELSB, FSK_PREAMBLE_LENGTH & 0xff)

        if fixLEN == 1:
            self._spi_write(REG_PAYLOADLENGTH, payload_len)
            self._spi_write(REG_PACKETCONFIG1, (self._spi_read(REG_PACKETCONFIG1) & RF_PACKETCONFIG1_CRC_MASK &
                    RF_PACKETCONFIG1_PACKETFORMAT_MASK) | RF_PACKETCONFIG1_PACKETFORMAT_FIXED | (FSK_CRC_ON << 4))
        else:
            self._spi_write(REG_PAYLOADLENGTH, 0xFF) # Set payload length to the maximum
            self._spi_write(REG_PACKETCONFIG1, (self._spi_read(REG_PACKETCONFIG1) & RF_PACKETCONFIG1_CRC_MASK &
                            RF_PACKETCONFIG1_PACKETFORMAT_MASK) | RF_PACKETCONFIG1_PACKETFORMAT_VARIABLE | (FSK_CRC_ON << 4))
        
    def GetFSkBandwidthRegValue(self, bandwidth):
        if bandwidth < 2600:
            print("Bandwidth is too low")
            return 0x00
        elif bandwidth < 3100:
            return 0x17
        elif bandwidth < 3900:
            return 0x0F
        elif bandwidth < 5200:
            return 0x07
        elif bandwidth < 6300:
            return 0x16
        elif bandwidth < 7800:
            return 0x0E
        elif bandwidth < 10400:
            return 0x06
        elif bandwidth < 12500:
            return 0x15
        elif bandwidth < 15600:
            return 0x0D
        elif bandwidth < 20800:
            return 0x05
        elif bandwidth < 25000:
            return 0x14
        elif bandwidth < 31300:
            return 0x0C
        elif bandwidth < 41700:
            return 0x04
        elif bandwidth < 50000:
            return 0x13
        elif bandwidth < 62500:
            return 0x0B
        elif bandwidth < 83333:
            return 0x03
        elif bandwidth < 100000:
            return 0x12
        elif bandwidth < 125000:
            return 0x0A
        elif bandwidth < 166700:
            return 0x02
        elif bandwidth < 200000:
            return 0x11
        elif bandwidth < 250000:
            return 0x09
        elif bandwidth < 300000:
            return 0x01
        else:
            print("Bandwidth is too high")
            return 0x00
        
    def SX1276SetRx_fsk(self):
        self._spi_write(REG_FSK_DIOMAPPING1, (self._spi_read(REG_FSK_DIOMAPPING1) & RF_DIOMAPPING1_DIO0_MASK & RF_DIOMAPPING1_DIO1_MASK & RF_DIOMAPPING1_DIO2_MASK) | 0x00 | 0x00 | 0x0C)
        self._spi_write(REG_FSK_DIOMAPPING2, (self._spi_read(REG_FSK_DIOMAPPING2) & RF_DIOMAPPING2_DIO4_MASK & RF_DIOMAPPING2_MAP_MASK) | 0xC0 | 0x01)
        self._spi_write(REG_RXCONFIG, RF_RXCONFIG_AFCAUTO_ON | RF_RXCONFIG_AGCAUTO_ON | RF_RXCONFIG_RXTRIGER_PREAMBLEDETECT)
        
        self._rx_buffer = []
        self._rx_payload_len = 0
        self._rssi = 0
        self.set_mode_rx_fsk()
       


    def on_recv(self, message):
        # This should be overridden by the user
        pass

    def sleep(self):
        if self._mode != MODE_SLEEP:
            with self._hw_lock:
                self._spi_write(REG_01_OP_MODE, MODE_SLEEP)
                self._mode = MODE_SLEEP

    def set_mode_tx_fsk(self):
        if self._mode != MODE_TX:
            with self._hw_lock:
                # self._spi_write(REG_40_DIO_MAPPING1, 0x40)  # Interrupt on TxDone
                self._spi_write(REG_40_DIO_MAPPING1, (self._spi_read(REG_40_DIO_MAPPING1) & RF_DIOMAPPING1_DIO0_MASK &
                                                                            RF_DIOMAPPING1_DIO1_MASK &
                                                                            RF_DIOMAPPING1_DIO2_MASK) | RF_DIOMAPPING1_DIO1_01)
                self._spi_write(REG_41_DIO_MAPPING2, (self._spi_read(REG_41_DIO_MAPPING2) & RF_DIOMAPPING2_DIO4_MASK &
                                                                            RF_DIOMAPPING2_MAP_MASK))
                self._spi_write(REG_01_OP_MODE, MODE_TX)
                self._mode = MODE_TX

    def set_mode_rx_fsk(self):
        if self._mode != MODE_RXCONTINUOUS:
            with self._hw_lock:
                temp = (self._spi_read(REG_01_OP_MODE) & RF_OPMODE_MASK)
                self._spi_write(REG_01_OP_MODE, temp | MODE_RXCONTINUOUS)
                self._mode = MODE_RXCONTINUOUS


    def wait_packet_sent(self):
        # wait for `_handle_interrupt` to switch the mode back
        start = time.time()
        while time.time() - start < self.wait_packet_sent_timeout:
            if self._mode != MODE_TX:
                return True

        return False

    def set_mode_idle(self):
        if self._mode != MODE_STDBY:
            with self._hw_lock:
                self._spi_write(REG_01_OP_MODE, MODE_STDBY)
                self._mode = MODE_STDBY


    def send_fsk(self, data):
        self.wait_packet_sent()
        self.set_mode_idle()
        # print(f'send {data} to {header_to}')
        # header = [header_to, self._this_address, header_id, header_flags]
        # if type(data) == int:
        #     data = [data]
        # elif type(data) == bytes:
        #     data = [p for p in data]
        if type(data) == str:
            data = [ord(s) for s in data]

        # if self.crypto:
        #     data = [b for b in self._encrypt(bytes(data))]

        payload = data
        
        if self.fixLEN == 0:
            with self._hw_lock:
                self._spi_write(REG_00_FIFO, len(payload))

                self._spi_write(REG_00_FIFO, payload)
        else:
            if self.payload_len != len(payload):
                print(f"Payload length is not equal to the set payload length {self.payload_len}")
                return False
            with self._hw_lock:
                self._spi_write(REG_PAYLOADLENGTH, len(payload))

                self._spi_write(REG_00_FIFO, payload)

        self.set_mode_tx_fsk()

        return True

    def _spi_write(self, register, payload):
        if type(payload) == int:
            payload = [payload]
        elif type(payload) == bytes:
            payload = [p for p in payload]
        elif type(payload) == str:
            payload = [ord(s) for s in payload]
        with self._hw_lock:
            self.spi.xfer([register | 0x80] + payload)

    def _spi_read(self, register, length=1):
        if length == 1:
            with self._hw_lock:
                d = self.spi.xfer([register] + [0] * length)[1]            
            return d
        else:
            with self._hw_lock:
                d = self.spi.xfer([register] + [0] * length)[1:]
            return d

    def _decrypt(self, message):
        decrypted_msg = self.crypto.decrypt(message)
        msg_length = decrypted_msg[0]
        return decrypted_msg[1:msg_length + 1]

    def _encrypt(self, message):
        msg_length = len(message)
        padding = bytes(((math.ceil((msg_length + 1) / 16) * 16) - (msg_length + 1)) * [0])
        msg_bytes = bytes([msg_length]) + message + padding
        encrypted_msg = self.crypto.encrypt(msg_bytes)
        return encrypted_msg

    def _handle_interrupt(self, channel):
        # print("interrupt 0 callback raised!\r\n")
        if self._mode == MODE_TX:
            self.sleep()
        elif self._mode == MODE_RXCONTINUOUS:
            if self.fixLEN == 0:
                self._rx_payload_len = self._spi_read(REG_00_FIFO)
                self._rx_buffer = self._spi_read(REG_00_FIFO, self._rx_payload_len)
            self._spi_write(REG_RXCONFIG, self._spi_read(REG_RXCONFIG) | RF_RXCONFIG_RESTARTRXWITHOUTPLLLOCK)
            self.on_recv(self._rx_buffer, self._rssi, self._received_msg_index)
            self._received_msg_index += 1
        return
    def _handle_interrupt1(self, channel):
        # print("interrupt 1 callback raised!\r\n")
        # TODO: fifo_interrupt when packet > FIFO_SIZE
        return
    
    def _handle_interrupt2(self, channel):
        # print("interrupt 2 callback raised!\r\n")
        if self._mode == MODE_RXCONTINUOUS:
            self._rssi = -(self._spi_read(REG_FSK_RSSIVALUE) >> 1)
        return 

    def close(self):
        GPIO.cleanup()
        self.spi.close()

    def __del__(self):
        self.close()
