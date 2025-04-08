# -*- coding: utf-8 -*-
# config_generator.py

import re
import logging
from typing import Dict, List

import config

log = logging.getLogger(__name__)


def _hex_string_to_bytes_array(hex_string: str) -> str:
    """
    Konwertuje ciąg znaków hex na formatowany tekst tablicy bajtów C.
    Na przykład: "deadbeef" -> "0xDE, 0xAD, 0xBE, 0xEF"
    """
    # Usuń wszystkie znaki niealfanumeryczne
    clean_hex = re.sub(r'[^0-9a-fA-F]', '', hex_string)

    # Dopilnuj parzystej liczby znaków
    if len(clean_hex) % 2 != 0:
        clean_hex = "0" + clean_hex

    # Podziel na pary znaków (bajty) i sformatuj
    byte_pairs = [clean_hex[i:i + 2] for i in range(0, len(clean_hex), 2)]
    bytes_array = [f"0x{pair.upper()}" for pair in byte_pairs]

    # Grupuj po 8 bajtów w linii (lub mniej dla ostatniej linii)
    lines = []
    for i in range(0, len(bytes_array), 8):
        line = ", ".join(bytes_array[i:i + 8])
        lines.append(line)

    return ",\n".join(lines)


def generate_config_c(remote_data: Dict) -> str:
    """
    Generuje plik konfiguracyjny config.c na podstawie danych pilota
    """
    try:
        # Konwersja identyfikatorów hex na format tablicy C
        pilot_id_bytes = _hex_string_to_bytes_array(remote_data["remote_id"])
        aes_key_bytes = _hex_string_to_bytes_array(remote_data["aes_key"])
        hmac_key_bytes = _hex_string_to_bytes_array(remote_data["hmac_key"])
        iv_bytes = _hex_string_to_bytes_array(remote_data["iv"])

        # Wypełnij szablon
        config_content = config.CONFIG_TEMPLATE.format(
            name=remote_data["name"],
            pilot_id_bytes=pilot_id_bytes,
            aes_key_bytes=aes_key_bytes,
            hmac_key_bytes=hmac_key_bytes,
            iv_bytes=iv_bytes
        )

        return config_content
    except Exception as e:
        log.error(f"Config Generator Error: Failed to generate config.c: {e}")
        raise


def generate_config_h() -> str:
    """
    Generuje plik nagłówkowy config.h
    """
    header = f"""/* Automatycznie wygenerowane przez ESZP Centralę v1.3 */
#ifndef CONFIG_H
#define CONFIG_H

#include <stdint.h>

#define PILOT_ID_LENGTH {config.PILOT_ID_LENGTH}
#define CRYPTO_AES_KEY_LENGTH {config.CRYPTO_AES_KEY_LENGTH}
#define CRYPTO_HMAC_KEY_LENGTH {config.CRYPTO_HMAC_KEY_LENGTH}
#define CRYPTO_IV_LENGTH {config.CRYPTO_IV_LENGTH}

extern const uint8_t PILOT_ID[PILOT_ID_LENGTH];
extern const uint8_t CRYPTO_AES_KEY[CRYPTO_AES_KEY_LENGTH];
extern const uint8_t CRYPTO_HMAC_KEY[CRYPTO_HMAC_KEY_LENGTH];
extern const uint8_t CRYPTO_IV[CRYPTO_IV_LENGTH];

#endif /* CONFIG_H */
"""
    return header