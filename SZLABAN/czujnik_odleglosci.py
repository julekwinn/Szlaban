#!/usr/bin/python3
# -*- coding: ascii -*-

import sys
import os
import time
import threading
from ctypes import CDLL, CFUNCTYPE, POINTER, c_int, c_uint, pointer, c_ubyte, c_uint8, c_uint32
import sysconfig
import site

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    lib_path = os.path.join(current_dir, 'vl53l0x_python.so')
    
    if not os.path.exists(lib_path):
        possible_locations = [
            os.path.join(current_dir, 'VL53L0X-python', 'bin', 'vl53l0x_python.so'),
            os.path.join(current_dir, 'VL53L0X-python', 'python', 'vl53l0x_python.cpython-311-aarch64-linux-gnu.so'),
        ]
        
        for loc in possible_locations:
            if os.path.exists(loc):
                lib_path = loc
                break
        else:
            raise OSError("VL53L0X library not found")
    
    _TOF_LIBRARY = CDLL(lib_path)
    
except Exception:
    raise OSError("Error loading VL53L0X library")

class Vl53l0xAccuracyMode:
    GOOD = 0
    BETTER = 1
    BEST = 2
    LONG_RANGE = 3
    HIGH_SPEED = 4

class Vl53l0xDeviceMode:
    SINGLE_RANGING = 0
    CONTINUOUS_RANGING = 1
    SINGLE_HISTOGRAM = 2
    CONTINUOUS_TIMED_RANGING = 3
    SINGLE_ALS = 10
    GPIO_DRIVE = 20
    GPIO_OSC = 21

class Vl53l0xGpioAlarmType:
    OFF = 0
    THRESHOLD_CROSSED_LOW = 1
    THRESHOLD_CROSSED_HIGH = 2
    THRESHOLD_CROSSED_OUT = 3
    NEW_MEASUREMENT_READY = 4

class Vl53l0xInterruptPolarity:
    LOW = 0
    HIGH = 1

class Vl53l0xError(RuntimeError):
    pass

_I2C_READ_FUNC = CFUNCTYPE(c_int, c_ubyte, c_ubyte, POINTER(c_ubyte), c_ubyte)
_I2C_WRITE_FUNC = CFUNCTYPE(c_int, c_ubyte, c_ubyte, POINTER(c_ubyte), c_ubyte)

try:
    import smbus
except ImportError:
    try:
        import smbus2 as smbus
    except ImportError:
        raise ImportError("smbus or smbus2 module required")

class VL53L0X:
    def __init__(self, i2c_bus=1, i2c_address=0x29, tca9548a_num=255, tca9548a_addr=0):
        self._i2c_bus = i2c_bus
        self.i2c_address = i2c_address
        self._tca9548a_num = tca9548a_num
        self._tca9548a_addr = tca9548a_addr
        self._i2c = smbus.SMBus()
        self._dev = None
        self.ADDR_UNIT_ID_HIGH = 0x16
        self.ADDR_UNIT_ID_LOW = 0x17
        self.ADDR_I2C_ID_HIGH = 0x18
        self.ADDR_I2C_ID_LOW = 0x19
        self.ADDR_I2C_SEC_ADDR = 0x8a

    def open(self):
        self._i2c.open(bus=self._i2c_bus)
        self._configure_i2c_library_functions()
        self._dev = _TOF_LIBRARY.initialise(self.i2c_address, self._tca9548a_num, self._tca9548a_addr)

    def close(self):
        self._i2c.close()
        self._dev = None

    def _configure_i2c_library_functions(self):
        def _i2c_read(address, reg, data_p, length):
            ret_val = 0
            result = []
            try:
                result = self._i2c.read_i2c_block_data(address, reg, length)
            except IOError:
                ret_val = -1
            if ret_val == 0:
                for index in range(length):
                    data_p[index] = result[index]
            return ret_val

        def _i2c_write(address, reg, data_p, length):
            ret_val = 0
            data = []
            for index in range(length):
                data.append(data_p[index])
            try:
                self._i2c.write_i2c_block_data(address, reg, data)
            except IOError:
                ret_val = -1
            return ret_val

        self._i2c_read_func = _I2C_READ_FUNC(_i2c_read)
        self._i2c_write_func = _I2C_WRITE_FUNC(_i2c_write)
        _TOF_LIBRARY.VL53L0X_set_i2c(self._i2c_read_func, self._i2c_write_func)

    def start_ranging(self, mode=Vl53l0xAccuracyMode.GOOD):
        _TOF_LIBRARY.startRanging(self._dev, mode)

    def stop_ranging(self):
        _TOF_LIBRARY.stopRanging(self._dev)

    def get_distance(self):
        return _TOF_LIBRARY.getDistance(self._dev)

    def get_timing(self):
        budget = c_uint(0)
        budget_p = pointer(budget)
        status = _TOF_LIBRARY.VL53L0X_GetMeasurementTimingBudgetMicroSeconds(self._dev, budget_p)
        if status == 0:
            return budget.value + 1000
        else:
            return 0

    def configure_gpio_interrupt(
            self, proximity_alarm_type=Vl53l0xGpioAlarmType.THRESHOLD_CROSSED_LOW,
            interrupt_polarity=Vl53l0xInterruptPolarity.HIGH, threshold_low_mm=250, threshold_high_mm=500):
        pin = c_uint8(0)
        device_mode = c_uint8(Vl53l0xDeviceMode.CONTINUOUS_RANGING)
        functionality = c_uint8(proximity_alarm_type)
        polarity = c_uint8(interrupt_polarity)
        status = _TOF_LIBRARY.VL53L0X_SetGpioConfig(self._dev, pin, device_mode, functionality, polarity)
        if status != 0:
            raise Vl53l0xError('GPIO config error')

        threshold_low = c_uint32(threshold_low_mm << 16)
        threshold_high = c_uint32(threshold_high_mm << 16)
        status = _TOF_LIBRARY.VL53L0X_SetInterruptThresholds(self._dev, device_mode, threshold_low, threshold_high)
        if status != 0:
            raise Vl53l0xError('Thresholds error')

        self.clear_interrupt()

    def clear_interrupt(self):
        mask = c_uint32(0)
        status = _TOF_LIBRARY.VL53L0X_ClearInterruptMask(self._dev, mask)
        if status != 0:
            raise Vl53l0xError('Interrupt clear error')

    def change_address(self, new_address):
        if self._dev is not None:
            raise Vl53l0xError('Address change error')

        self._i2c.open(bus=self._i2c_bus)

        if new_address is None or new_address == self.i2c_address:
            return
        else:
            high = self._i2c.read_byte_data(self.i2c_address, self.ADDR_UNIT_ID_HIGH)
            low = self._i2c.read_byte_data(self.i2c_address, self.ADDR_UNIT_ID_LOW)
            self._i2c.write_byte_data(self.i2c_address, self.ADDR_I2C_ID_HIGH, high)
            self._i2c.write_byte_data(self.i2c_address, self.ADDR_I2C_ID_LOW, low)
            self._i2c.write_byte_data(self.i2c_address, self.ADDR_I2C_SEC_ADDR, new_address)
            self.i2c_address = new_address

        self._i2c.close()

class CzujnikOdleglosci:
    TRYB_GOOD = 0
    TRYB_BETTER = 1
    TRYB_BEST = 2
    TRYB_LONG_RANGE = 3
    TRYB_HIGH_SPEED = 4

    def __init__(self, i2c_bus=1, i2c_address=0x29, tryb=TRYB_BETTER):
        self.tof = VL53L0X(i2c_bus=i2c_bus, i2c_address=i2c_address)
        self.tryb = tryb
        self.odleglosc_mm = 0
        self.odleglosc_cm = 0
        self.pomiar_aktywny = False
        self.watek_pomiaru = None
        self.interwal_pomiaru = 0.5

    def inicjalizuj(self):
        try:
            self.tof.open()
            return True
        except Exception:
            return False

    def zamknij(self):
        self.zatrzymaj_pomiary()
        try:
            self.tof.close()
        except Exception:
            pass

    def zmien_adres(self, nowy_adres):
        try:
            self.tof.change_address(nowy_adres)
            return True
        except Exception:
            return False

    def wykonaj_pojedynczy_pomiar(self):
        try:
            tryb_vl53l0x = self._konwertuj_tryb()
            self.tof.start_ranging(tryb_vl53l0x)
            time.sleep(0.05)
            odleglosc = self.tof.get_distance()
            self.tof.stop_ranging()
            
            if odleglosc > 0:
                self.odleglosc_mm = odleglosc
                self.odleglosc_cm = odleglosc / 10
                return self.odleglosc_cm
            else:
                return -1
        except Exception:
            return -1

    def _konwertuj_tryb(self):
        if self.tryb == self.TRYB_GOOD:
            return Vl53l0xAccuracyMode.GOOD
        elif self.tryb == self.TRYB_BETTER:
            return Vl53l0xAccuracyMode.BETTER
        elif self.tryb == self.TRYB_BEST:
            return Vl53l0xAccuracyMode.BEST
        elif self.tryb == self.TRYB_LONG_RANGE:
            return Vl53l0xAccuracyMode.LONG_RANGE
        elif self.tryb == self.TRYB_HIGH_SPEED:
            return Vl53l0xAccuracyMode.HIGH_SPEED
        else:
            return Vl53l0xAccuracyMode.BETTER

    def _watek_ciagly_pomiar(self):
        try:
            tryb_vl53l0x = self._konwertuj_tryb()
            self.tof.start_ranging(tryb_vl53l0x)
            
            while self.pomiar_aktywny:
                odleglosc = self.tof.get_distance()
                if odleglosc > 0:
                    self.odleglosc_mm = odleglosc
                    self.odleglosc_cm = odleglosc / 10
                time.sleep(self.interwal_pomiaru)
                
            self.tof.stop_ranging()
        except Exception:
            self.pomiar_aktywny = False

    def rozpocznij_ciagly_pomiar(self, interwal=0.5):
        if self.pomiar_aktywny:
            return False
        
        try:
            self.interwal_pomiaru = interwal
            self.pomiar_aktywny = True
            self.watek_pomiaru = threading.Thread(target=self._watek_ciagly_pomiar)
            self.watek_pomiaru.daemon = True
            self.watek_pomiaru.start()
            return True
        except Exception:
            self.pomiar_aktywny = False
            return False

    def zatrzymaj_pomiary(self):
        self.pomiar_aktywny = False
        if self.watek_pomiaru:
            self.watek_pomiaru.join(timeout=1.0)
            self.watek_pomiaru = None

    def pobierz_odleglosc_mm(self):
        return self.odleglosc_mm

    def pobierz_odleglosc_cm(self):
        return self.odleglosc_cm
    
    def ustaw_tryb_pomiaru(self, tryb):
        if tryb in [self.TRYB_GOOD, self.TRYB_BETTER, self.TRYB_BEST, self.TRYB_LONG_RANGE, self.TRYB_HIGH_SPEED]:
            self.tryb = tryb
        else:
            self.tryb = self.TRYB_BETTER
        
        if self.pomiar_aktywny:
            aktywny = self.pomiar_aktywny
            interwal = self.interwal_pomiaru
            self.zatrzymaj_pomiary()
            if aktywny:
                self.rozpocznij_ciagly_pomiar(interwal)

    def dostepne_tryby_pomiaru(self):
        return {
            "GOOD": "Szybki pomiar (33ms), zasieg 1.2m",
            "BETTER": "Sredni pomiar (66ms), zasieg 1.2m",
            "BEST": "Dokladny pomiar (200ms), zasieg 1.2m",
            "LONG_RANGE": "Daleki zasieg (33ms), zasieg 2m",
            "HIGH_SPEED": "Bardzo szybki (20ms), zasieg 1.2m"
        }