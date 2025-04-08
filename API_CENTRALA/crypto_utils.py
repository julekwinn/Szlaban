# -*- coding: utf-8 -*-
# crypto_utils.py

import logging
import binascii
import hmac
import hashlib
import struct
from typing import Tuple, Optional, Dict

from Crypto.Cipher import AES
from Crypto.Util import Counter  # Używamy Counter dla AES-CTR
# Usunęliśmy import unpad, bo AES-CTR go nie używa

log = logging.getLogger(__name__)

HMAC_SIZE = 32  # SHA-256

def decode_hex(hex_str: str) -> bytes:
    """Konwertuje ciąg znaków hex na bajty."""
    try:
        return binascii.unhexlify(hex_str)
    except (binascii.Error, TypeError) as e:
        log.error(f"Hex Decode Error for '{hex_str}': {e}")
        raise ValueError(f"Invalid hex string: {e}")


def verify_remote_message_ctr(encrypted_hex: str, remote_data: Dict) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Weryfikuje zaszyfrowaną wiadomość od pilota przy użyciu AES-CTR i HMAC-SHA256.

    Pobiera klucze i ID z remote_data (słownik z bazy danych).
    Oczekiwany format remote_data:
    {
        'remote_id': 'hex_string_id',  # 8 bajtów ID pilota
        'aes_key': 'hex_string_aes_key', # 16 bajtów klucza AES
        'hmac_key': 'hex_string_hmac_key',# 32 bajty klucza HMAC
        'iv': 'hex_string_iv' # 16 bajtów IV dla licznika AES-CTR
    }

    Format zaszyfrowanej wiadomości (hex):
    [n bajtów zaszyfrowanych danych][32 bajty HMAC]

    Zdekodowane dane powinny zawierać (zgodnie z crypto_decoder.py):
    [8 bajtów PILOT_ID][8 bajtów COUNTER][opcjonalne bajty komendy]

    Zwraca:
    - (True, counter_value, None) w przypadku powodzenia
    - (False, None, opis_błędu) w przypadku niepowodzenia
    """
    try:
        # Pobierz i zdekoduj dane pilota i wiadomość
        log.debug(f"Verifying message for remote_id (hex): {remote_data.get('remote_id')}")
        db_remote_id_bytes = decode_hex(remote_data['remote_id'])
        db_aes_key_bytes = decode_hex(remote_data['aes_key'])
        db_hmac_key_bytes = decode_hex(remote_data['hmac_key'])
        db_iv_bytes = decode_hex(remote_data['iv'])
        encrypted_data_bytes = decode_hex(encrypted_hex)

        # Sprawdź minimalną długość (co najmniej 8 bajtów ID + 8 bajtów licznika = 16 bajtów payloadu + HMAC)
        expected_min_payload_len = 16 # 8 bajtów ID + 8 bajtów Counter
        if len(encrypted_data_bytes) < (expected_min_payload_len + HMAC_SIZE):
            log.warning(f"Message too short: {len(encrypted_data_bytes)} bytes, expected >= {expected_min_payload_len + HMAC_SIZE}")
            return False, None, "message_too_short"

        # 1. Podziel na część zaszyfrowaną i HMAC
        encrypted_part = encrypted_data_bytes[:-HMAC_SIZE]
        received_hmac = encrypted_data_bytes[-HMAC_SIZE:]
        log.debug(f"Encrypted part (len {len(encrypted_part)}): {encrypted_part.hex()}")
        log.debug(f"Received HMAC (len {len(received_hmac)}): {received_hmac.hex()}")

        # 2. Oblicz oczekiwany HMAC
        h = hmac.new(db_hmac_key_bytes, encrypted_part, hashlib.sha256)
        calculated_hmac = h.digest()
        log.debug(f"Calculated HMAC: {calculated_hmac.hex()}")

        # 3. Porównaj HMAC (bezpieczne porównanie)
        if not hmac.compare_digest(received_hmac, calculated_hmac):
            log.warning("HMAC verification failed.")
            return False, None, "hmac_verification_failed"
        log.debug("HMAC verification successful.")

        # 4. Deszyfruj dane używając AES-CTR
        try:
            # Utwórz licznik AES-CTR na podstawie IV z bazy
            # Wartość początkowa licznika to IV zinterpretowane jako liczba całkowita big-endian
            initial_counter_value = int.from_bytes(db_iv_bytes, byteorder='big')
            ctr = Counter.new(128, initial_value=initial_counter_value)
            cipher = AES.new(db_aes_key_bytes, AES.MODE_CTR, counter=ctr)

            decrypted_data = cipher.decrypt(encrypted_part)
            log.debug(f"Decrypted data (len {len(decrypted_data)}): {decrypted_data.hex()}")

        except Exception as e:
            log.error(f"AES-CTR Decryption failed: {e}", exc_info=True)
            return False, None, "decryption_error"

        # 5. Wyodrębnij ID pilota i licznik z odszyfrowanych danych
        if len(decrypted_data) < expected_min_payload_len:
            log.warning(f"Decrypted data too short: {len(decrypted_data)} bytes, expected >= {expected_min_payload_len}")
            return False, None, "decrypted_data_too_short"

        decrypted_id = decrypted_data[:8]
        # Zakładamy 8-bajtowy licznik, jak w crypto_decoder.py
        decrypted_counter_bytes = decrypted_data[8:16]
        # Opcjonalnie reszta to komenda, ignorujemy ją na razie
        # command_bytes = decrypted_data[16:]

        log.debug(f"Decrypted Pilot ID: {decrypted_id.hex()}")
        log.debug(f"Expected Pilot ID:  {db_remote_id_bytes.hex()}")
        log.debug(f"Decrypted Counter Bytes: {decrypted_counter_bytes.hex()}")

        # 6. Sprawdź, czy ID pilota z wiadomości zgadza się z ID pilota z bazy danych
        if decrypted_id != db_remote_id_bytes:
            log.warning("Decrypted Pilot ID does not match expected remote ID.")
            return False, None, "invalid_remote_id"
        log.debug("Decrypted Pilot ID matches.")

        # 7. Wyciągnij wartość licznika (8 bajtów, big-endian unsigned long long)
        try:
            # '>Q' oznacza big-endian unsigned long long (8 bajtów)
            counter_value = struct.unpack('>Q', decrypted_counter_bytes)[0]
            log.debug(f"Decrypted Counter Value: {counter_value}")
        except struct.error as e:
            log.error(f"Failed to unpack counter bytes: {e}", exc_info=True)
            return False, None, "invalid_counter_format"

        # Wszystko się zgadza
        log.info(f"Message verified successfully for remote ID {remote_data['remote_id']}. Counter: {counter_value}")
        return True, counter_value, None

    except ValueError as e: # Błąd dekodowania hex
        log.error(f"Data decoding error: {e}", exc_info=True)
        return False, None, "invalid_hex_data"
    except KeyError as e: # Brak klucza w remote_data
        log.error(f"Missing key in remote_data dictionary: {e}", exc_info=True)
        return False, None, "missing_remote_key_data"
    except Exception as e:
        log.error(f"Unexpected error during message verification: {e}", exc_info=True)
        # Zwracamy ogólny błąd, aby nie ujawniać szczegółów implementacji
        return False, None, "verification_error"