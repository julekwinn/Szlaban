# radio_processor.py
# -*- coding: utf-8 -*-

import logging

log = logging.getLogger(__name__)

# Hardkodowane ID użytkownika zwracane dla każdego (niepustego) sygnału radiowego
HARDCODED_RADIO_USER_ID = "radio_user_test_001"

def process_radio_data(raw_data) -> dict:
    """
    Przetwarza surowe dane radiowe. Zawsze zwraca ustalone ID i valid=True
    (jeśli dane nie są puste), ignorując treść danych.

    Zwraca:
        dict: Słownik {'valid': bool, 'user_id': str | None}
    """
    return {'valid': True, 'user_id': "Pilot Juliusza"}
