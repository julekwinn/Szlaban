#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import time
import signal
import threading
import logging
import requests
import json 
from datetime import datetime
from flask import Flask, jsonify, request
from rich.logging import RichHandler
from rich.traceback import install as rich_traceback_install

# Importy lokalnych modulow
try:
    from szlaban import Barrier, Config as BarrierConfig
    from radio_handle import RadioHandler, RadioMode
    from radio_processor import process_radio_data
except ImportError as e:
    print(f"[BŁĄD KRYTYCZNY] ImportError: {e}. Sprawdź pliki: szlaban.py, radio_handle.py, radio_processor.py.")
    sys.exit(1)

# --- Konfiguracja Aplikacji ---
class AppConfig:
    API_HOST = '0.0.0.0'
    API_PORT = 5000
    RADIO_MODE = RadioMode.FSK
    AUTO_CLOSE_DELAY = 10.0
    LOG_LEVEL = "INFO"
    # Adres URL endpointu centrali do wysyłania zdarzeń
    CENTRAL_ENDPOINT_URL = 'http://192.168.182.240:5002/barrier/event' # URL lub None, jak jwst none to sie nie wysla wiadomosci do centrali po prostu
    CENTRAL_VERIFY_URL = 'http://192.168.182.240:5002/api/verify/remote' # URL lub None, jeśli None, weryfikacja nie działa
    # Unikalne ID tego szlabanu
    BARRIER_ID = "testbarrier"

# --- Inicjalizacja Logowania ---
rich_traceback_install(show_locals=False)
logging.basicConfig(
    level=AppConfig.LOG_LEVEL,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(markup=True, show_path=False)]
)
log = logging.getLogger(__name__)

# --- Zmienne Globalne ---
barrier = None
radio_handler = None
service_mode = False
auto_close_thread = None
running = True
state_lock = threading.Lock() # Lock do ochrony dostępu do zmiennych globalnych

# --- Inicjalizacja API Flask ---
app = Flask(__name__)
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.ERROR) # Zmniejsz gadatliwość logów Flask/Werkzeug

# --- Funkcje powiadomień ---
def send_notification_async(payload):
    """Wysyła powiadomienie do centrali w osobnym wątku."""
    target_url = AppConfig.CENTRAL_ENDPOINT_URL
    if not target_url:
        # Logujemy tylko raz w send_notification, że wysyłanie jest wyłączone
        return

    # Logowanie DOKŁADNIE przed wysłaniem
    # Używamy json.dumps dla ładniejszego formatowania payloadu w logach
    payload_str = json.dumps(payload, indent=2, ensure_ascii=False)
    log.debug(f"Wątek powiadomienia: Próba wysłania do [bold blue]{target_url}[/]:\n{payload_str}")

    try:
        response = requests.post(target_url, json=payload, timeout=10)
        response.raise_for_status() # Rzuci wyjątkiem dla statusów 4xx/5xx
        log.info(f"Powiadomienie wysłane pomyślnie do [bold blue]{target_url}[/] (Status: {response.status_code}). Typ: {payload.get('event_type', 'N/A')}")
    except requests.exceptions.Timeout:
         log.error(f"Błąd wysyłania powiadomienia do [bold red]{target_url}[/]: Timeout (po 10s).")
    except requests.exceptions.ConnectionError:
         log.error(f"Błąd wysyłania powiadomienia do [bold red]{target_url}[/]: Błąd połączenia (sprawdź adres IP/dostępność sieci).")
    except requests.exceptions.HTTPError as e:
         # Błąd odpowiedzi HTTP (np. 404 Not Found, 500 Internal Server Error)
         log.error(f"Błąd wysyłania powiadomienia do [bold red]{target_url}[/]: Błąd HTTP {e.response.status_code}. Odpowiedź: {e.response.text[:200]}") # Pokaż początek odpowiedzi błędu
    except requests.exceptions.RequestException as e:
         # Inne błędy związane z żądaniem
         log.error(f"Błąd wysyłania powiadomienia do [bold red]{target_url}[/]: Błąd żądania: {e}")
    except Exception as e:
         # Niespodziewane błędy
         log.exception(f"Niespodziewany błąd podczas wysyłania powiadomienia do {target_url}:")

# ZMODYFIKOWANA FUNKCJA
def send_notification(event_type: str, trigger_method: str, user_id: str = None, success: bool = True, details: str = None):
    """Przygotowuje payload i uruchamia wysyłkę w osobnym wątku."""
    timestamp = datetime.now().isoformat()
    payload = {
        "barrier_id": AppConfig.BARRIER_ID,
        "event_type": event_type if success else "barrier_failure",
        "trigger_method": trigger_method,
        "timestamp": timestamp,
        "user_id": user_id if user_id is not None else "system",
        "success": success,
    }
    if details:
        payload["details"] = details
    if not success:
        failed_action = "unknown"
        if event_type == "barrier_opened": failed_action = "open"
        if event_type == "barrier_closed": failed_action = "close"
        payload["failed_action"] = failed_action

    # Logowanie ZANIM wątek zostanie uruchomiony
    log.info(f"Przygotowano zdarzenie: Typ='{payload['event_type']}', Trigger='{trigger_method}', User='{payload['user_id']}', Success={success}")

    target_url = AppConfig.CENTRAL_ENDPOINT_URL
    if target_url:
        log.debug(f"Uruchamianie wysyłki powiadomienia do: [bold blue]{target_url}[/]")
        notification_thread = threading.Thread(target=send_notification_async, args=(payload,), daemon=True)
        notification_thread.start()
    else:
        log.warning("Wysyłanie powiadomień do centrali jest WYŁĄCZONE (CENTRAL_ENDPOINT_URL jest None).")


# --- Funkcje operacji szlabanu ---
def execute_barrier_open(trigger_method: str, user_id: str = None):
    log.debug(f"Watek Otwierania: Start (Trigger: {trigger_method}, User: {user_id})")
    success = False
    details = "Barrier not initialized"
    if barrier:
        try:
            success = barrier.open()
            details = "Otwarcie szlabanu zakończone." if success else "Nieudana próba otwarcia szlabanu."
            if success:
                start_auto_close_timer_if_needed()
        except Exception as e:
            log.exception(f"Błąd podczas barrier.open() wywołanego przez {trigger_method}:")
            success = False
            details = f"Wyjątek podczas otwierania: {e}"
    else:
        log.error("execute_barrier_open: barrier object does not exist!")

    send_notification(event_type="barrier_opened", trigger_method=trigger_method, user_id=user_id, success=success, details=details)
    log.debug(f"Watek Otwierania: Koniec (Success: {success})")
    return success

def execute_barrier_close(trigger_method: str, user_id: str = None):
    log.debug(f"Watek Zamykania: Start (Trigger: {trigger_method}, User: {user_id})")
    success = False
    details = "Barrier not initialized"
    if barrier:
        try:
            success = barrier.close()
            details = "Zamknięcie szlabanu zakończone." if success else "Nieudana próba zamknięcia szlabanu."
        except Exception as e:
            log.exception(f"Błąd podczas barrier.close() wywołanego przez {trigger_method}:")
            success = False
            details = f"Wyjątek podczas zamykania: {e}"
    else:
        log.error("execute_barrier_close: barrier object does not exist!")

    send_notification(event_type="barrier_closed", trigger_method=trigger_method, user_id=user_id, success=success, details=details)
    log.debug(f"Watek Zamykania: Koniec (Success: {success})")
    return success

def execute_service_end_close(user_id: str = "system"):
    log.info(f"Watek Zamykania (Service End): Start (User: {user_id})")
    close_success = False
    details = "Barrier not initialized"
    if barrier:
        try:
            close_success = barrier.close()
            details = "Zamknięcie szlabanu po trybie serwisowym." if close_success else "Nieudane zamknięcie szlabanu po trybie serwisowym."
        except Exception as e:
            log.exception(f"Błąd podczas barrier.close() w execute_service_end_close:")
            close_success = False
            details = f"Wyjątek podczas zamykania po serwisie: {e}"
    else:
        log.error("execute_service_end_close: barrier object does not exist!")

    send_notification(event_type="barrier_closed", trigger_method="service_end", user_id=user_id, success=close_success, details=details)

    with state_lock:
        global service_mode
        if close_success:
            if service_mode:
                log.info("Zamkniecie udane. Wylaczanie trybu serwisowego.")
                service_mode = False
                send_notification(event_type="service_mode_ended", trigger_method="service_end", user_id=user_id, success=True)
            else:
                log.warning("execute_service_end_close: Zamknięcie udane, ale tryb serwisowy był już wyłączony?")
        else:
            log.warning("Zamkniecie nieudane. Pozostawianie trybu serwisowego.")
            send_notification(event_type="service_mode_ended", trigger_method="service_end", user_id=user_id, success=False, details="Failed to close barrier.")

    log.info(f"Watek Zamykania (Service End): Koniec. service_mode={service_mode}")

# --- Funkcje pomocnicze ---
def start_auto_close_timer_if_needed():
    global auto_close_thread
    with state_lock:
        if service_mode or not barrier or not barrier.is_open or barrier.in_motion:
            return
        if auto_close_thread and auto_close_thread.is_alive():
            return

        log.info(f"Timer: Uruchamianie auto-zamkniecia za {AppConfig.AUTO_CLOSE_DELAY:.1f}s...")
        auto_close_thread = threading.Thread(target=auto_close_task, daemon=True)
        auto_close_thread.start()

def auto_close_task():
    try:
        time.sleep(AppConfig.AUTO_CLOSE_DELAY)
        log.info("Timer: Czas minal, proba zamkniecia.")
        should_close = False
        with state_lock:
            if service_mode:
                log.info("Timer: Auto-zamkniecie przerwane - tryb serwisowy.")
                return
            if barrier and barrier.is_open and not barrier.in_motion:
                log.info("Timer: Stan OK do auto-zamknięcia.")
                should_close = True
            else:
                reason = "stan nieznany"
                if barrier:
                    if not barrier.is_open: reason = "szlaban już zamknięty"
                    elif barrier.in_motion: reason = "szlaban w ruchu"
                log.info(f"Timer: Auto-zamkniecie niepotrzebne ({reason}).")

        if should_close:
            close_thread = threading.Thread(target=execute_barrier_close, args=("auto_close", None), daemon=True)
            close_thread.start()
    except Exception as e:
        log.exception(f"Timer: Blad w watku auto-zamkniecia:")

# --- Obsługa radia ---
def handle_radio_data(data: bytes, rssi=None, index=None):
    """
    Obsługuje dane odebrane z radia. Ignoruje je, jeśli szlaban jest
    otwarty, w ruchu lub w trybie serwisowym. W przeciwnym razie
    wysyła dane do weryfikacji w centrali za pomocą process_radio_data
    i jeśli weryfikacja się powiedzie, inicjuje otwarcie szlabanu.
    """
    log.debug(f"[Radio]: Odebrano {len(data)} bajtów (RSSI: {rssi}, Index: {index}).")
    with state_lock:
        ignore_reason = None
        if service_mode:
            ignore_reason = "Tryb serwisowy aktywny"
        elif not barrier:
            log.error("[Radio]: Krytyczny błąd - Barrier object nie istnieje!")
            ignore_reason = "Obiekt szlabanu niezainicjalizowany"
        elif barrier.in_motion:
            ignore_reason = "Szlaban w ruchu"
        elif barrier.is_open:
            ignore_reason = "Szlaban już otwarty"

        if ignore_reason:
            log.debug(f"[Radio]: Ignorowanie sygnału - {ignore_reason}.")
            return
    log.debug("[Radio]: Stan szlabanu OK (zamknięty, nie w ruchu), przystępowanie do weryfikacji sygnału...")

    processing_result = process_radio_data(
        raw_data=data,
        verify_url=AppConfig.CENTRAL_VERIFY_URL,
        barrier_id=AppConfig.BARRIER_ID
    )

    if processing_result.get('valid'):
        user_id = processing_result.get('user_id') # 'verified_remote'
        log.info(f"[Radio]: Sygnał zweryfikowany przez centralę (User: {user_id}, RSSI: {rssi}). Otwieranie.")
        open_thread = threading.Thread(target=execute_barrier_open, args=("radio", user_id), daemon=True)
        open_thread.start()
    else:
        log.info(f"[Radio]: Sygnał odrzucony podczas weryfikacji w centrali (RSSI: {rssi}).")

# --- Funkcja zamykania systemu ---
def shutdown_system(signum=None, frame=None):
    global running, radio_handler, barrier
    if not running: return
    running = False

    trigger = "signal" if signum else "unknown_exit"
    if signum == signal.SIGINT: trigger = "keyboard_interrupt"
    elif signum == signal.SIGTERM: trigger = "terminate_signal"

    log.warning(f"\nShutdown: Zamykanie systemu (Trigger: {trigger})...")
    send_notification(event_type="system_shutdown_initiated", trigger_method=trigger, user_id=None)
    time.sleep(0.2)

    if radio_handler:
        log.info("Shutdown: Zamykanie radia...")
        try: radio_handler.cleanup()
        except Exception: log.exception("Shutdown: Blad zamykania radia:")

    if barrier:
        log.info("Shutdown: Zamykanie szlabanu (GPIO cleanup)...")
        try: barrier.shutdown()
        except Exception: log.exception("Shutdown: Blad zamykania szlabanu:")

    log.warning("Shutdown: System zamkniety.")
    time.sleep(0.1)
    sys.exit(0)

# --- Endpointy API ---
@app.route('/status', methods=['GET'])
def get_status():
    with state_lock:
        if not barrier: return jsonify({"error": "Barrier not initialized"}), 500
        try:
            b_status = barrier.status()
        except Exception as e:
            log.exception("Błąd podczas pobierania statusu szlabanu:")
            return jsonify({"error": "Failed to get barrier status"}), 500
        s_mode = service_mode
    return jsonify({"barrier_status": b_status, "service_mode": s_mode})

@app.route('/open', methods=['POST'])
def api_open():
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        log.warning("API Open: Żądanie odrzucone - brak nagłówka X-User-ID.")
        return jsonify({"status": "error", "message": "Missing X-User-ID header."}), 400

    log.info(f"API Open: Żądanie (User: {user_id})")
    with state_lock:
        if not barrier: return jsonify({"error": "Barrier not initialized"}), 500
        if service_mode: return jsonify({"status": "error", "message": "Service mode active."}), 409
        if barrier.in_motion: return jsonify({"status": "ok", "message": "Barrier in motion."}), 200
        if barrier.is_open: return jsonify({"status": "ok", "message": "Barrier already open."}), 200

        log.info(f"API Open: Inicjowanie otwierania przez {user_id}")
        open_thread = threading.Thread(target=execute_barrier_open, args=("api", user_id), daemon=True)
        open_thread.start()
        return jsonify({"status": "ok", "message": "Opening initiated."}), 202

@app.route('/close', methods=['POST'])
def api_close():
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        log.warning("API Close: Żądanie odrzucone - brak nagłówka X-User-ID.")
        return jsonify({"status": "error", "message": "Missing X-User-ID header."}), 400

    log.info(f"API Close: Żądanie (User: {user_id})")
    with state_lock:
        if not barrier: return jsonify({"error": "Barrier not initialized"}), 500
        if service_mode: return jsonify({"status": "error", "message": "Service mode active."}), 409
        if barrier.in_motion: return jsonify({"status": "ok", "message": "Barrier in motion."}), 200
        if not barrier.is_open: return jsonify({"status": "ok", "message": "Barrier already closed."}), 200

        log.info(f"API Close: Inicjowanie zamykania przez {user_id}")
        close_thread = threading.Thread(target=execute_barrier_close, args=("api", user_id), daemon=True)
        close_thread.start()
        return jsonify({"status": "ok", "message": "Closing initiated."}), 202

@app.route('/service/start', methods=['POST'])
def api_service_start():
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        log.warning("API Service Start: Żądanie odrzucone - brak nagłówka X-User-ID.")
        return jsonify({"status": "error", "message": "Missing X-User-ID header."}), 400

    log.info(f"API Service Start: Żądanie (User: {user_id})")
    with state_lock:
        global service_mode
        if not barrier: return jsonify({"error": "Barrier not initialized"}), 500
        if service_mode:
            return jsonify({"status": "ok", "message": "Service mode already active."}), 200

        log.warning(f"API Service Start: Włączanie trybu serwisowego przez {user_id}.")
        service_mode = True
        send_notification(event_type="service_mode_started", trigger_method="api", user_id=user_id)

        should_open = False
        if not barrier.is_open and not barrier.in_motion:
            log.info("API Service Start: Szlaban zamknięty, inicjowanie otwierania.")
            should_open = True
            response_code = 202
            response_message = "Service mode enabled. Opening initiated."
        else:
            log.info(f"API Service Start: Tryb serwisowy włączony (szlaban {'open' if barrier.is_open else 'in motion'}).")
            response_code = 200
            response_message = f"Service mode enabled (barrier {'open' if barrier.is_open else 'in motion'})."

    if should_open:
        open_thread = threading.Thread(target=execute_barrier_open, args=("service_start", user_id), daemon=True)
        open_thread.start()

    return jsonify({"status": "ok", "message": response_message}), response_code

@app.route('/service/end', methods=['POST'])
def api_service_end():
    global service_mode
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        log.warning("API Service End: Żądanie odrzucone - brak nagłówka X-User-ID.")
        return jsonify({"status": "error", "message": "Missing X-User-ID header."}), 400

    log.info(f"API Service End: Żądanie (User: {user_id})")
    send_notification(event_type="service_mode_ending_attempt", trigger_method="api", user_id=user_id)

    action = None
    with state_lock:
        if not barrier: return jsonify({"error": "Barrier not initialized"}), 500
        if not service_mode: action = 'error_not_in_service'
        elif barrier.is_open and not barrier.in_motion: action = 'close'
        elif barrier.in_motion: action = 'error_motion'
        else: action = 'disable_only'

    if action == 'error_not_in_service':
        return jsonify({"status": "ok", "message": "Service mode was not active."}), 200
    elif action == 'error_motion':
        log.warning("API Service End: Nie można zakończyć - szlaban w ruchu.")
        send_notification(event_type="service_mode_ending_attempt", trigger_method="api", user_id=user_id, success=False, details="Cannot end service mode while barrier is in motion.")
        return jsonify({"status": "error", "message": "Cannot end service mode while barrier is in motion."}), 409
    elif action == 'close':
        log.info("API Service End: Inicjowanie zamykania szlabanu.")
        close_thread = threading.Thread(target=execute_service_end_close, args=(user_id,), daemon=True)
        close_thread.start()
        return jsonify({"status": "ok", "message": "Attempting to end service mode by closing the barrier."}), 202
    elif action == 'disable_only':
        log.warning("API Service End: Wyłączanie trybu (szlaban już zamknięty).")
        with state_lock:
            service_mode = False
        send_notification(event_type="service_mode_ended", trigger_method="api", user_id=user_id, success=True, details="Barrier was already closed.")
        return jsonify({"status": "ok", "message": "Service mode disabled (barrier was already closed)."}), 200
    else:
        log.error("API Service End: Niespodziewany stan wewnętrzny.")
        return jsonify({"error": "Internal server error"}), 500

# --- Główna część skryptu ---
if __name__ == "__main__":
    log.info("="*30 + " Inicjalizacja Systemu Szlabanu " + "="*30)
    log.info(f"ID Szlabanu: {AppConfig.BARRIER_ID}")
    if AppConfig.CENTRAL_ENDPOINT_URL:
        log.info(f"Endpoint powiadomień centrali: {AppConfig.CENTRAL_ENDPOINT_URL}")
    else:
        log.warning("Wysyłanie powiadomień do centrali jest WYŁĄCZONE (CENTRAL_ENDPOINT_URL).")
    if AppConfig.CENTRAL_VERIFY_URL:
         log.info(f"Endpoint weryfikacji centrali: {AppConfig.CENTRAL_VERIFY_URL}")
    else:
         log.warning("Weryfikacja radiowa w centrali jest WYŁĄCZONA (CENTRAL_VERIFY_URL).")


    try:
        log.info("Inicjalizacja Barrier...")
        barrier_config = BarrierConfig()
        barrier = Barrier(config=barrier_config)
        log.info(f"Barrier init OK (GPIO: {barrier.gpio_ready}, Sensor: {barrier.sensor_ready})")
        if barrier.gpio_ready:
            try: barrier._set_led(barrier.status())
            except Exception: log.exception("Błąd ustawiania LED:")
        send_notification(event_type="system_startup", trigger_method="init", user_id=None)
    except Exception as e:
        log.exception("KRYTYCZNY BŁĄD inicjalizacji Barrier:")
        send_notification(event_type="system_failure", trigger_method="init", user_id=None, success=False, details=f"Barrier init failed: {e}")
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()
            log.info("GPIO cleanup po błędzie inicjalizacji.")
        except ImportError: pass
        except Exception: log.exception("Błąd GPIO cleanup po błędzie inicjalizacji:")
        sys.exit(1)

    try:
        log.info(f"Inicjalizacja Radio Handler (tryb: {AppConfig.RADIO_MODE})...")
        radio_handler = RadioHandler(mode=AppConfig.RADIO_MODE, data_callback=handle_radio_data)
        log.info("Radio Handler init OK.")
    except Exception as e:
        log.exception("BŁĄD inicjalizacji Radio Handler:")
        send_notification(event_type="system_warning", trigger_method="init", user_id=None, success=False, details=f"Radio Handler init failed: {e}")
        radio_handler = None

    signal.signal(signal.SIGINT, shutdown_system)
    signal.signal(signal.SIGTERM, shutdown_system)

    log.info(f"Start API na http://{AppConfig.API_HOST}:{AppConfig.API_PORT}...")
    api_thread = threading.Thread(
        target=lambda: app.run(host=AppConfig.API_HOST, port=AppConfig.API_PORT, debug=False, use_reloader=False),
        daemon=True
    )
    api_thread.start()

    log.info("="*30 + " System Gotowy " + "="*30)

    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt received, shutting down...")
    except Exception as e:
        log.exception("Niespodziewany błąd pętli głównej:")
        send_notification(event_type="system_failure", trigger_method="main_loop", user_id=None, success=False, details=f"Unexpected error: {e}")
        if running: shutdown_system()
    finally:
        if running:
            log.info("Main loop finished, ensuring shutdown...")
            shutdown_system()