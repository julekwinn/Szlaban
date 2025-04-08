# radio_processor.py
# -*- coding: utf-8 -*-

import logging
import binascii # Potrzebne do konwersji bytes -> hex
import requests
from typing import Dict, Optional

log = logging.getLogger(__name__)

VERIFIED_USER_PLACEHOLDER = "verified_remote"

# Funkcja ZNÓW OCZEKUJE raw_data jako bytes!
def process_radio_data(raw_data: bytes, verify_url: Optional[str], barrier_id: str) -> Dict[str, Optional[str]]:
    """
    Przetwarza surowe dane radiowe (bajty).
    1. Konwertuje dane na hex.
    2. Wysyła je do centrali (na podany verify_url) w celu weryfikacji.
    3. Zwraca słownik wskazujący, czy dostęp został przyznany przez centralę.

    Args:
        raw_data: Surowe bajty odebrane z modułu radiowego.
        verify_url: Adres URL endpointu weryfikacji w centrali.
        barrier_id: ID tego konkretnego szlabanu.

    Returns:
        dict: Słownik {'valid': bool, 'user_id': str | None}
    """
    # Usuwamy print, bo wiemy już co jest problemem
    #print(f"DEBUG PRINT [process_radio_data]: Otrzymano raw_data = {raw_data!r}")

    if not verify_url:
        log.warning("Weryfikacja w centrali WYŁĄCZONA (brak URL). Dostęp ZAWSZE odrzucony.")
        return {'valid': False, 'user_id': None}

    # Sprawdź czy otrzymaliśmy niepuste bajty
    if not raw_data or not isinstance(raw_data, bytes):
        log.warning(f"Nieprawidłowe dane radiowe (oczekiwano bytes, otrzymano: {type(raw_data)})")
        return {'valid': False, 'user_id': None}

    # Krok 1: Konwertuj surowe bajty na string hex
    try:
        # ----> TA LINIA JEST KLUCZOWA - konwertuje bytes na hex <----
        hex_data = binascii.hexlify(raw_data).decode('ascii')
        log.debug(f"Dane przekonwertowane na hex (dł: {len(hex_data)}): {hex_data[:64]}...")
    except Exception as e:
        log.exception(f"Błąd konwersji danych (bytes) na hex: {e}")
        return {'valid': False, 'user_id': None}

    # Krok 2: Przygotuj payload dla centrali
    payload = {
        "barrier_id": barrier_id,
        "encrypted_data": hex_data # Wysyłamy string hex
    }
    log.debug(f"Wysyłanie żądania weryfikacji do {verify_url} dla barrier_id: {barrier_id}")

    # Krok 3: Wyślij zapytanie do centrali i obsłuż odpowiedź
    try:
        response = requests.post(verify_url, json=payload, timeout=5)

        if response.status_code == 200:
            try:
                response_data = response.json()
                access_granted = response_data.get("access_granted", False)
                reason = response_data.get("reason", "brak informacji")
                if access_granted:
                    log.info(f"Weryfikacja w centrali: SUKCES (Dostęp przyznany)")
                    return {'valid': True, 'user_id': VERIFIED_USER_PLACEHOLDER}
                else:
                    log.warning(f"Weryfikacja w centrali: ODMOWA (Powód: {reason})")
                    return {'valid': False, 'user_id': None}
            except requests.exceptions.JSONDecodeError:
                log.error(f"Błąd weryfikacji: Centrala zwróciła status 200, ale odpowiedź nie jest poprawnym JSON-em: {response.text}")
                return {'valid': False, 'user_id': None}
        else:
            log.error(f"Błąd weryfikacji: Centrala odpowiedziała statusem {response.status_code}. Treść: {response.text}")
            return {'valid': False, 'user_id': None}

    except requests.exceptions.Timeout:
        log.error(f"Błąd weryfikacji: Timeout podczas połączenia z {verify_url}")
        return {'valid': False, 'user_id': None}
    except requests.exceptions.RequestException as e:
        log.error(f"Błąd weryfikacji: Błąd sieci podczas połączenia z centralą: {e}")
        return {'valid': False, 'user_id': None}
    except Exception as e:
        log.exception("Niespodziewany błąd podczas weryfikacji sygnału w centrali:")
        return {'valid': False, 'user_id': None}