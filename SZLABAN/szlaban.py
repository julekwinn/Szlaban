#!/usr/bin/python3
# -*- coding: utf-8 -*-

import RPi.GPIO as GPIO
import time
import threading
import signal
import sys
import logging # <-- Dodaj import logging

# Utwórz logger dla tego modułu
log = logging.getLogger(__name__) # Użyj __name__ jako nazwy loggera

try:
    # Upewnij się, że ten plik jest w tej samej lokalizacji lub w PYTHONPATH
    from czujnik_szlaban import CzujnikSzlaban
except ImportError:
    # Użyj loggera do ostrzeżenia
    log.warning("Nie można zaimportować CzujnikSzlaban. Funkcje czujnika będą niedostępne.")
    CzujnikSzlaban = None # Pozwala na bezpieczne sprawdzanie 'if CzujnikSzlaban:'

class Config:
    # Ustawienia czasowe
    OPEN_TIME = 5.0      # sekundy
    CLOSE_TIME = 10.0    # sekundy
    RETRY_DELAY = 10.0   # sekundy
    MAX_CLOSE_ATTEMPTS = 3 # liczba prob

    # Ustawienia czujnika
    DISTANCE_THRESHOLD = 50.0 # cm
    I2C_BUS = 1
    I2C_ADDRESS = 0x29

    # Piny GPIO
    PIN_RED = 6          # Czerwony (zamkniety)
    PIN_GREEN = 26       # Zielony (otwarty)
    PIN_BLUE = 5         # Niebieski (w ruchu)

    # Ustawienia migania
    BLINK_INTERVAL = 0.2   # sekundy (okres migania)
    ERROR_BLINKS = 5     # ilosc migniec podczas bledu

class Barrier:
    def __init__(self, config=Config()):
        # Przekaż konfigurację do loggera, jeśli chcesz logować wartości configu
        log.debug(f"Inicjalizacja Barrier z konfiguracją: {config.__dict__}")
        self.config = config
        self.is_open = False
        self.in_motion = False
        self.stop_closing = False
        self.sensor_ready = False
        self.gpio_ready = False
        self.blink_thread = None
        self.blink_active = False
        self.sensor = None
        self._sensor_lock = threading.Lock()

        self._init_gpio()
        self._initialize_and_start_sensor()

    def _initialize_and_start_sensor(self):
        """Initialize the sensor and start continuous ranging immediately."""
        if not CzujnikSzlaban:
            log.warning("Init Sensor: Moduł CzujnikSzlaban niedostępny.")
            self.sensor_ready = False
            return

        log.debug("Init Sensor: Zdobywanie blokady sensora...")
        with self._sensor_lock:
            log.info("Init Sensor: Rozpoczynanie inicjalizacji i startu pomiaru...")
            try:
                self.sensor = CzujnikSzlaban(
                    i2c_bus=self.config.I2C_BUS,
                    i2c_address=self.config.I2C_ADDRESS
                )
                init_ok = self.sensor.inicjalizuj() # Ta metoda może logować wewnętrznie
                if not init_ok:
                    log.error("Init Sensor: FAILED (inicjalizuj() zwróciło False)")
                    self.sensor = None
                    self.sensor_ready = False
                    return

                log.info("Init Sensor: Inicjalizacja udana.")
                log.info("Init Sensor: Uruchamianie pomiaru ciągłego...")
                self.sensor.uruchom_ciagly_pomiar(0.1) # Interwał pomiaru
                log.info("Init Sensor: Pomiar ciągły uruchomiony.")
                self.sensor_ready = True

            except Exception as e:
                # Użyj log.exception dla automatycznego dodania tracebacku
                log.exception("Init Sensor: Wyjątek podczas inicjalizacji/startu:")
                self.sensor_ready = False
                self.sensor = None
        log.debug("Init Sensor: Zwolniono blokadę sensora.")


    def _init_gpio(self):
        """Inicjalizacja GPIO dla diod LED"""
        log.info("Init GPIO: Konfiguracja pinów GPIO...")
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(self.config.PIN_RED, GPIO.OUT)
            GPIO.setup(self.config.PIN_GREEN, GPIO.OUT)
            GPIO.setup(self.config.PIN_BLUE, GPIO.OUT)
            self._set_led('off')
            self.gpio_ready = True
            log.info("Init GPIO: [bold green]Sukces[/].")
        except Exception as e:
            log.exception("Init GPIO: [bold red]FAILED[/]:")
            self.gpio_ready = False

    def _set_led(self, state):
        """Sterowanie diodą RGB"""
        if not self.gpio_ready:
            log.debug(f"Set LED: Próba ustawienia '{state}', ale GPIO niegotowe.")
            return
        log.debug(f"Set LED: Ustawianie stanu '{state}'")
        self._stop_blinking() # Stop blinking (logs internally if needed)
        GPIO.output(self.config.PIN_RED, GPIO.LOW)
        GPIO.output(self.config.PIN_GREEN, GPIO.LOW)
        GPIO.output(self.config.PIN_BLUE, GPIO.LOW)
        if state == 'closed': GPIO.output(self.config.PIN_RED, GPIO.HIGH)
        elif state == 'open': GPIO.output(self.config.PIN_GREEN, GPIO.HIGH)
        elif state == 'moving': self._start_blue_blinking()
        elif state == 'error': self._error_blink()

    def _blue_blink_thread(self):
        """Wątek migania diody niebieskiej"""
        log.debug("Blink Thread: Start")
        while self.blink_active:
            if self.gpio_ready:
                GPIO.output(self.config.PIN_BLUE, GPIO.HIGH)
                time.sleep(self.config.BLINK_INTERVAL)
                if not self.blink_active: break
                GPIO.output(self.config.PIN_BLUE, GPIO.LOW)
                time.sleep(self.config.BLINK_INTERVAL)
            else:
                log.warning("Blink Thread: GPIO niegotowe, zatrzymywanie wątku.")
                break
        log.debug("Blink Thread: Koniec")

    def _start_blue_blinking(self):
        """Rozpoczyna miganie diody niebieskiej w oddzielnym wątku"""
        log.debug("Start Blink: Rozpoczynanie migania na niebiesko...")
        self._stop_blinking() # Zatrzymaj poprzednie miganie
        self.blink_active = True
        self.blink_thread = threading.Thread(target=self._blue_blink_thread)
        self.blink_thread.daemon = True
        self.blink_thread.start()

    def _stop_blinking(self):
        """Zatrzymuje miganie diody"""
        if self.blink_thread and self.blink_thread.is_alive():
            log.debug("Stop Blink: Zatrzymywanie aktywnego wątku migania...")
            self.blink_active = False # Sygnalizuj zakonczenie
            self.blink_thread.join(timeout=0.5)
            if self.blink_thread.is_alive():
                log.warning("Stop Blink: Wątek migania nie zakończył się w czasie.")
            else:
                log.debug("Stop Blink: Wątek migania zakończony.")
        self.blink_thread = None
        if self.gpio_ready: GPIO.output(self.config.PIN_BLUE, GPIO.LOW)

    def _error_blink(self):
        """Miganie diodą w trybie awaryjnym"""
        log.warning("Error Blink: Aktywacja sekwencji błędu!")
        self._stop_blinking()
        if self.gpio_ready:
            for _ in range(10):
                GPIO.output(self.config.PIN_RED, GPIO.HIGH); time.sleep(0.2)
                GPIO.output(self.config.PIN_RED, GPIO.LOW); time.sleep(0.2)
            log.info("Error Blink: Pauza przed ustawieniem stanu 'Otwarty'.")
            time.sleep(2.0)
            log.info("Error Blink: Ustawianie stanu 'Otwarty' jako bezpiecznego po błędzie.")
            self._set_led('open')
            self.is_open = True; self.in_motion = False
        else: log.error("Error Blink: Nie można migać - GPIO niegotowe!")

    def _obstacle_blink(self):
        """Miganie na czerwono po wykryciu przeszkody"""
        log.warning("Obstacle Blink: Wykryto przeszkodę - aktywacja migania!")
        self._stop_blinking()
        if self.gpio_ready:
            for _ in range(self.config.ERROR_BLINKS):
                GPIO.output(self.config.PIN_RED, GPIO.HIGH); time.sleep(self.config.BLINK_INTERVAL)
                GPIO.output(self.config.PIN_RED, GPIO.LOW); time.sleep(self.config.BLINK_INTERVAL)
            log.debug("Obstacle Blink: Zakończono miganie.")
        else: log.error("Obstacle Blink: Nie można migać - GPIO niegotowe!")


    # --- Metody zwiazane z czujnikiem ---

    def _get_distance(self):
        """Pobiera aktualną odległość (zakłada ciągły pomiar)"""
        if not self.sensor_ready or not self.sensor: return -1
        distance = -1
        log.debug("Get Distance: Zdobywanie blokady sensora...")
        with self._sensor_lock:
             log.debug("Get Distance: Blokada zdobyta.")
             try:
                 distance = self.sensor.pobierz_aktualna_odleglosc()
                 log.debug(f"Get Distance: Odczytano dystans = {distance} cm")
             except Exception as e:
                 log.error(f"Get Distance: Błąd podczas odczytu dystansu: {e}")
                 distance = -1
        log.debug("Get Distance: Zwolniono blokadę sensora.")
        return distance

    def _check_obstacle_during_closing(self, attempt):
        """Sprawdzanie przeszkód podczas zamykania (zakłada ciągły pomiar)"""
        if not self.sensor_ready:
            log.warning("Check Obstacle: Czujnik niedostępny. Zakładanie BRAKU przeszkody.")
            time.sleep(self.config.CLOSE_TIME) # Symuluj czas bez sprawdzania
            return True

        start_time = time.time()
        remaining_time = self.config.CLOSE_TIME
        log.info(f"Check Obstacle: Rozpoczęto pętlę sprawdzania (Próba {attempt})...")

        last_logged_dist = -100 # Zapobiega zbyt częstemu logowaniu tego samego dystansu
        log_interval = 1.0 # Loguj dystans co 1 sekundę
        last_log_time = time.time()

        while remaining_time > 0:
            if self.stop_closing:
                log.warning("Check Obstacle: Otrzymano żądanie zatrzymania.")
                return False

            distance = self._get_distance()

            # Loguj dystans okresowo lub gdy sie zmieni znaczaco
            current_time = time.time()
            if distance >= 0 and (abs(distance - last_logged_dist) > 1 or current_time - last_log_time > log_interval):
                 log.debug(f"Check Obstacle: Dystans={distance:.1f}cm, Pozostało={remaining_time:.1f}s")
                 last_logged_dist = distance
                 last_log_time = current_time
            # Zastąpiono szybkie drukowanie w konsoli logowaniem DEBUG
            # print(f"\rProba {attempt}/{self.config.MAX_CLOSE_ATTEMPTS} - Zamykanie... D:{distance if distance >= 0 else '--'} Pozostalo: {remaining_time:.1f}s", end="")

            if 0 < distance < self.config.DISTANCE_THRESHOLD:
                log.warning(f"Check Obstacle: [bold yellow]Wykryto przeszkodę![/] Odległość: {distance:.1f}cm")
                self.stop_closing = True
                self._obstacle_blink() # Loguje wewnętrznie
                return False

            time.sleep(0.1)
            remaining_time = self.config.CLOSE_TIME - (time.time() - start_time)

        # Usunięto czyszczenie linii print
        log.info(f"Check Obstacle: Pętla zakończona (Próba {attempt}), nie wykryto przeszkody.")
        return True

    # --- Metody publiczne ---

    def open(self):
        """Otwarcie szlabanu"""
        if self.is_open and not self.in_motion: log.info("Open: Szlaban już otwarty."); return True
        if self.in_motion: log.warning("Open: Próba otwarcia podczas ruchu - ignorowanie."); return False

        log.info("[bold green]Open[/]: Rozpoczynanie otwierania...")
        self.in_motion = True
        self._set_led('moving') # Loguje wewnętrznie
        # Symulacja czasu otwierania
        log.debug(f"Open: Oczekiwanie {self.config.OPEN_TIME}s...")
        time.sleep(self.config.OPEN_TIME)
        # Zakonczenie otwierania
        self.is_open = True
        self.in_motion = False
        self._set_led('open') # Loguje wewnętrznie
        log.info("[bold green]Open[/]: Szlaban [green]OTWARTY[/].")
        return True

    def close(self):
        """Proba zamkniecia szlabanu"""
        if not self.is_open and not self.in_motion: log.info("Close: Szlaban już zamknięty."); return True
        if self.in_motion: log.warning("Close: Próba zamknięcia podczas ruchu - ignorowanie."); return False

        log.info("[bold blue]Close[/]: Rozpoczynanie sekwencji zamykania...")
        closing_success = False
        for attempt in range(1, self.config.MAX_CLOSE_ATTEMPTS + 1):
            log.info(f"Close: [blue]Próba {attempt}/{self.config.MAX_CLOSE_ATTEMPTS}[/]")

            # Start/Stop monitoringu nie jest już tutaj potrzebny

            self.in_motion = True
            self.stop_closing = False # Resetuj flagę dla tej próby
            self._set_led('moving')

            # Sprawdzanie przeszkód
            closing_check_result = self._check_obstacle_during_closing(attempt) # Loguje wewnętrznie

            self.in_motion = False # Koniec ruchu (udanego lub nie)

            if closing_check_result:
                self.is_open = False
                self._set_led('closed')
                log.info(f"Close: Próba {attempt} [bold green]udana[/]. Szlaban [red]ZAMKNIĘTY[/].")
                closing_success = True
                break # Sukces, zakończ pętlę prób
            else:
                log.warning(f"Close: Próba {attempt} [bold red]nieudana[/] (przeszkoda/błąd/stop).")
                self.is_open = True # Szlaban POZOSTAJE OTWARTY
                self._set_led('open') # Ustaw na zielono

                if attempt == self.config.MAX_CLOSE_ATTEMPTS:
                    log.error("Close: [bold red]ALARM![/] Nie udało się zamknąć szlabanu po maksymalnej liczbie prób!")
                    self._error_blink() # Loguje wewnętrznie
                    closing_success = False
                else:
                    log.info(f"Close: Oczekiwanie [yellow]{self.config.RETRY_DELAY}s[/] przed kolejną próbą...")
                    self._set_led('closed') # Czerwony podczas czekania
                    time.sleep(self.config.RETRY_DELAY)
                    self._set_led('open') # Zielony przed następną próbą

        if not closing_success:
            log.warning("Close: Sekwencja zamykania zakończona [bold red]niepowodzeniem[/]. Szlaban pozostaje OTWARTY.")
            self.is_open = True
            self.in_motion = False

        return closing_success

    def status(self):
        """Aktualny status szlabanu"""
        # Ta metoda jest szybka, nie wymaga logowania za każdym razem
        if self.in_motion: return "W ruchu"
        return "Otwarty" if self.is_open else "Zamkniety"



    def shutdown(self):
        """Bezpieczne zamkniecie systemu (bardziej odporne na wielokrotne wywołanie)."""
        log.warning("[[bold orange_red1]Shutdown Barrier[/]]: Rozpoczynanie procedury wyłączania...")

        # 1. Zatrzymaj wątek migania (bez operacji GPIO jeśli to możliwe)
        if self.blink_thread and self.blink_thread.is_alive():
            log.debug("Shutdown Barrier: Zatrzymywanie wątku migania...")
            self.blink_active = False
            self.blink_thread.join(timeout=0.5) # Poczekaj chwilę
            if self.blink_thread.is_alive():
                log.warning("Shutdown Barrier: Wątek migania nie zakończył się w czasie.")
        self.blink_thread = None
        # Nie próbuj tutaj wyłączać diody GPIO, zrobi to cleanup

        # 2. Zatrzymaj i zamknij sensor
        # Sprawdzamy self.sensor zamiast self.sensor_ready, bo ready moglo byc False po bledzie
        if self.sensor:
             log.info("[Shutdown Barrier]: Zatrzymywanie pomiaru i zamykanie obiektu czujnika...")
             with self._sensor_lock:
                 try:
                     log.debug("Shutdown Barrier: Zatrzymywanie pomiaru ciągłego...")
                     # Sprawdz czy metoda istnieje przed wywolaniem
                     if callable(getattr(self.sensor, "zatrzymaj_ciagly_pomiar", None)):
                         self.sensor.zatrzymaj_ciagly_pomiar()
                         log.info("Shutdown Barrier: Pomiar ciągły zatrzymany.")
                     else:
                         log.debug("Shutdown Barrier: Metoda zatrzymaj_ciagly_pomiar niedostepna.")
                 except Exception:
                     log.exception("Shutdown Barrier: Błąd podczas zatrzymywania pomiaru:")
                 try:
                     log.debug("Shutdown Barrier: Zamykanie obiektu czujnika (zamknij())...")
                     # Sprawdz czy metoda istnieje przed wywolaniem
                     if callable(getattr(self.sensor, "zamknij", None)):
                         self.sensor.zamknij()
                         log.info("Shutdown Barrier: Obiekt czujnika zamknięty.")
                     else:
                         log.debug("Shutdown Barrier: Metoda zamknij niedostepna.")
                 except Exception:
                     log.exception("Shutdown Barrier: Błąd podczas zamykania obiektu czujnika:")
             self.sensor = None
             self.sensor_ready = False # Zresetuj flagę gotowości
             log.info("[Shutdown Barrier]: Zasoby czujnika zwolnione.")
        else:
             log.debug("[Shutdown Barrier]: Obiekt czujnika nie istniał.")

        # 3. Wyczyść GPIO TYLKO RAZ
        # Sprawdzamy flagę gpio_ready, aby uniknąć wielokrotnego cleanup
        if self.gpio_ready:
            log.info("[Shutdown Barrier]: Czyszczenie GPIO...")
            try:
                # GPIO.cleanup() resetuje WSZYSTKIE kanały i tryb numeracji
                GPIO.cleanup()
                self.gpio_ready = False # << Ustaw na False OD RAZU po cleanup
                log.info("[Shutdown Barrier]: GPIO wyczyszczone.")
            except Exception as e:
                # Runtime error moze sie zdarzyc jesli cleanup zostanie jakos wywolane wczesniej
                log.error(f"Shutdown Barrier: Błąd podczas GPIO.cleanup(): {e}")
                # Mimo błędu, ustawiamy na False, bo stan GPIO jest niepewny
                self.gpio_ready = False
        else:
            log.debug("[Shutdown Barrier]: GPIO nie było zainicjalizowane lub już wyczyszczone.")

        log.warning("[[bold orange_red1]Shutdown Barrier[/]]: Procedura wyłączania zakończona.")

# --- Koniec definicji klasy Barrier ---

# --- Kod testowy (jeśli uruchomiono bezpośrednio szlaban.py) ---
if __name__ == "__main__":
    # Skonfiguruj podstawowe logowanie tylko dla testu tego modułu
    # Użyj formatu podobnego do RichHandlera dla spójności
    logging.basicConfig(
        level=logging.DEBUG, # Ustaw DEBUG dla testów
        format='%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%H:%M:%S'
    )

    log.info("-" * 30)
    log.info(" Uruchomiono test modulu szlaban.py")
    log.info(" (Continuous Ranging Strategy + Logging)")
    log.info("-" * 30)
    barrier = Barrier() # Sensor initializes and starts ranging here

    def handle_sigint(sig, frame):
        log.warning("\nSIGINT Otrzymany w tescie szlaban.py")
        if 'barrier' in locals() and barrier: barrier.shutdown()
        sys.exit(0)
    signal.signal(signal.SIGINT, handle_sigint)

    try:
        if not barrier.sensor_ready:
            log.error("Test: Czujnik nie zostal poprawnie zainicjalizowany/uruchomiony. Przerywanie testu.")
            sys.exit(1)
        else:
             log.info("Test: Czujnik zainicjalizowany i pomiar uruchomiony.")

        log.info("\n--- Test: Otwieranie ---")
        barrier.open()
        log.info(f"Status: {barrier.status()}")
        time.sleep(1)

        log.info("\n--- Test: Zamykanie (z symulacja przeszkody) ---")
        log.warning(f"!!! Ustaw przeszkode blizej niz {barrier.config.DISTANCE_THRESHOLD} cm !!!")
        time.sleep(3)
        if barrier.close():
            log.info("Test: Zamkniecie zakonczone sukcesem.")
        else:
            log.warning("Test: Zamkniecie nie powiodlo sie (prawdopodobnie przez przeszkode).")
        log.info(f"Status: {barrier.status()}")
        time.sleep(1)

        if barrier.is_open:
            log.info("\n--- Test: Ponowna proba zamkniecia (bez przeszkody) ---")
            log.warning("!!! Usun przeszkode !!!")
            time.sleep(3)
            if barrier.close():
                log.info("Test: Druga proba zamkniecia zakonczona sukcesem.")
            else:
                log.error("Test: Druga proba zamkniecia nie powiodla sie.")
            log.info(f"Status: {barrier.status()}")
            time.sleep(1)

    except Exception as e:
        log.exception("Wystapil blad podczas testu:")
    finally:
        log.info("\n--- Test: Konczenie pracy ---")
        # barrier.shutdown() # Wywolywane przez handler SIGINT
        log.info("Test zakonczony.")