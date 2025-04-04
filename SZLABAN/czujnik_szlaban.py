#!/usr/bin/python3
# -*- coding: ascii -*-

import time
import sys
import os
import threading
from contextlib import redirect_stdout, redirect_stderr

# Redirect output before importing sensor library
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

# Import sensor library
from czujnik_odleglosci import CzujnikOdleglosci

# Restore original output
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__

class CzujnikSzlaban:
    def __init__(self, i2c_bus=1, i2c_address=0x29, tryb=CzujnikOdleglosci.TRYB_HIGH_SPEED):
        # Store original output streams
        self._original_stdout = sys.__stdout__
        self._original_stderr = sys.__stderr__
        
        # Redirect output before sensor init
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')
        
        try:
            self.czujnik = CzujnikOdleglosci(i2c_bus, i2c_address, tryb)
        finally:
            # Restore output after init
            sys.stdout = self._original_stdout
            sys.stderr = self._original_stderr
            
        self.jest_aktywny = False
        self.monitorowanie_aktywne = False
        self.watek_monitorowania = None
        self.wynik_monitorowania = None
        self.aktualna_odleglosc = 0
    
    def _silent_call(self, func, *args, **kwargs):
        """Execute function in silent mode"""
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')
        try:
            return func(*args, **kwargs)
        finally:
            sys.stdout = self._original_stdout
            sys.stderr = self._original_stderr
    
    def inicjalizuj(self):
        result = self._silent_call(self.czujnik.inicjalizuj)
        if result:
            self.jest_aktywny = True
        return result
    
    def uruchom_ciagly_pomiar(self, interwal=0.1):
        if not self.jest_aktywny:
            return False
        return self._silent_call(self.czujnik.rozpocznij_ciagly_pomiar, interwal)
    
    def zatrzymaj_ciagly_pomiar(self):
        if self.jest_aktywny:
            self._silent_call(self.czujnik.zatrzymaj_pomiary)
    
    def pobierz_aktualna_odleglosc(self):
        if self.jest_aktywny:
            return self._silent_call(self.czujnik.pobierz_odleglosc_cm)
        return -1
    
    def monitoruj(self, prog_odleglosci_cm, czas_monitorowania_s=15):
        if not self.jest_aktywny:
            return False
        
        czas_poczatkowy = time.time()
        
        while time.time() - czas_poczatkowy < czas_monitorowania_s:
            aktualna_odleglosc = self.pobierz_aktualna_odleglosc()
            self.aktualna_odleglosc = aktualna_odleglosc
            
            if aktualna_odleglosc > 0 and aktualna_odleglosc < prog_odleglosci_cm:
                return False
            
            time.sleep(0.05)
        
        return True
    
    def zamknij(self):
        self._silent_call(self.zatrzymaj_ciagly_pomiar)
        self._silent_call(self.czujnik.zamknij)
        self.jest_aktywny = False