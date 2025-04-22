#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
import sqlite3  # Wciąż potrzebne dla type hint w zależnościach
from datetime import datetime
from typing import List, Optional
from contextlib import asynccontextmanager
import json 
import uvicorn

from fastapi import FastAPI, HTTPException, status, Depends, Request, Security 
from fastapi.responses import Response # Dodajemy Response

try:
    import config
    import crypto_utils
    import models  
    import db     
    import core    
    import config_generator  
except ImportError as e:
    print(f"[BŁĄD KRYTYCZNY] Nie można zaimportować modułu: {e}. Sprawdź, czy pliki config.py, crypto_utils.py, models.py, db.py, core.py, config_generator.py istnieją i są dostępne.")
    exit(1)

# --- Konfiguracja Logowania ---
log_format = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO), format=log_format)
log = logging.getLogger(__name__)

logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
logging.getLogger('fastapi').setLevel(logging.WARNING)


# --- Lifespan FastAPI ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Zarządza cyklem życia aplikacji FastAPI (start/stop)."""
    log.info("Uruchamianie serwera centrali ESZP...")
    try:
        db.init_db()  # Uruchom inicjalizację bazy przy starcie
        log.info("Inicjalizacja bazy danych zakończona pomyślnie.")
    except Exception as e:
        log.exception("KRYTYCZNY BŁĄD podczas inicjalizacji bazy danych!")
    yield
    log.info("Zamykanie serwera centrali ESZP...")


# --- Aplikacja FastAPI ---
app = FastAPI(
    title="Centrala ESZP v1.4 (Remotes Extension)",
    description="API do zarządzania i kontroli szlabanów oraz pilotów.",
    version="1.4.0",
    lifespan=lifespan,
)


# --- Endpointy API ---

# == Grupa: Events (Zdarzenia od Szlabanów) ==
@app.post("/barrier/event", status_code=status.HTTP_200_OK, tags=["Events"])
async def receive_barrier_event_endpoint(event_data: models.BarrierEventDBInput, request: Request):
    """Odbiera zdarzenie od kontrolera szlabanu i zapisuje do bazy."""
    client_ip = request.client.host if request.client else "N/A"
    received_time = datetime.now().isoformat()

    # Logowanie odebranego zdarzenia
    try:
        event_payload_str = json.dumps(event_data.model_dump(), indent=2, ensure_ascii=False)
        log.info(f"Odebrano zdarzenie od szlabanu (IP: {client_ip}):\n{event_payload_str}")
    except Exception as e:
        log.error(f"Błąd podczas formatowania odebranego zdarzenia do logów: {e}")
        log.info(f"Odebrano zdarzenie od szlabanu (IP: {client_ip}), surowe dane: {event_data!r}")

    # Próba zapisu do bazy
    if db.add_event_to_db(event_data, received_time):
        log.debug(f"Zdarzenie (Barrier: {event_data.barrier_id}, Type: {event_data.event_type}) zapisane pomyślnie.")
        return {"status": "received_ok", "received_at": received_time}
    else:
        log.error(f"Nie udało się zapisać zdarzenia do bazy danych! (Barrier: {event_data.barrier_id}, Type: {event_data.event_type})")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save event data.")


# == Grupa: Admin (Zarządzanie Systemem - Wymaga Tokena Admina) ==
@app.get("/api/events", response_model=List[models.BarrierEventDBResponse], tags=["Admin"],
         dependencies=[Depends(core.verify_admin_token)])
async def get_all_events_endpoint(limit: int = config.DEFAULT_EVENT_LIMIT):
    """(Admin) Pobiera ostatnie zdarzenia ze WSZYSTKICH szlabanów."""
    log.info(f"Admin: Żądanie pobrania ostatnich {limit} zdarzeń.")
    events = db.get_events_from_db(barrier_ids=None, limit=limit, only_failures=False)
    if events is None:
        log.error("Admin: Błąd pobierania zdarzeń z bazy danych dla endpointu /api/events.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to retrieve events from database.")
    log.debug(f"Admin: Zwrócono {len(events)} zdarzeń.")
    return events


@app.post("/api/users", response_model=models.UserResponse, status_code=status.HTTP_201_CREATED, tags=["Admin"],
          dependencies=[Depends(core.verify_admin_token)])
async def create_user_endpoint(user_data: models.UserCreate):
    """(Admin) Tworzy nowego użytkownika."""
    log.info(f"Admin: Żądanie utworzenia użytkownika '{user_data.username}'.")
    existing_user = db.get_user_by_username(user_data.username)
    if existing_user:
        log.warning(f"Admin: Próba utworzenia istniejącego użytkownika: '{user_data.username}'")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Username '{user_data.username}' already exists.")

    hashed_password = core.get_password_hash(user_data.password)
    user_id = db.create_db_user(user_data.username, hashed_password)
    if user_id:
        log.info(f"Admin: Utworzono użytkownika '{user_data.username}' (ID: {user_id}).")
        return models.UserResponse(id=user_id, username=user_data.username)
    else:
        log.error(f"Admin: Nieudane tworzenie użytkownika '{user_data.username}' w bazie danych.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error creating user.")


@app.post("/api/barriers", response_model=models.BarrierResponse, status_code=status.HTTP_201_CREATED, tags=["Admin"],
          dependencies=[Depends(core.verify_admin_token)])
async def add_barrier_endpoint(barrier_data: models.BarrierCreate):
    """(Admin) Dodaje nowy szlaban (rejestruje jego ID i URL)."""
    log.info(f"Admin: Żądanie dodania szlabanu '{barrier_data.barrier_id}' (URL: {barrier_data.controller_url}).")
    if not barrier_data.controller_url.startswith(("http://", "https://")):
        log.warning(f"Admin: Próba dodania szlabanu z niepoprawnym URL: {barrier_data.controller_url}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid controller_url format (must start with http:// or https://).")

    db_id = db.create_db_barrier(barrier_data.barrier_id, barrier_data.controller_url)
    if db_id:
        log.info(f"Admin: Dodano szlaban '{barrier_data.barrier_id}' (URL: {barrier_data.controller_url}).")
        return models.BarrierResponse(id=db_id, **barrier_data.model_dump())
    else:
        conn_check = None
        exists = None
        try:
            conn_check = db.get_db()
            cursor_check = conn_check.cursor()
            cursor_check.execute(f"SELECT 1 FROM {config.TABLE_BARRIERS} WHERE barrier_id=? OR controller_url=?",
                                (barrier_data.barrier_id, barrier_data.controller_url))
            exists = cursor_check.fetchone()
        except Exception as e:
             log.error(f"Admin: Błąd podczas sprawdzania istnienia szlabanu/URL: {e}")
        finally:
            if conn_check:
                 conn_check.close()

        if exists:
            log.warning(f"Admin: Próba dodania istniejącego szlabanu/URL: ID='{barrier_data.barrier_id}', URL='{barrier_data.controller_url}'")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="Barrier ID or Controller URL already exists.")
        else:
            log.error(f"Admin: Nieudane dodanie szlabanu '{barrier_data.barrier_id}' do bazy danych (nieznany błąd).")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Database error adding barrier.")


@app.post("/api/permissions", response_model=models.PermissionResponse, status_code=status.HTTP_201_CREATED,
          tags=["Admin"], dependencies=[Depends(core.verify_admin_token)])
async def grant_permission_endpoint(permission_data: models.PermissionCreate):
    """(Admin) Nadaje użytkownikowi uprawnienia do szlabanu."""
    log.info(f"Admin: Żądanie nadania uprawnienia '{permission_data.permission_level}' użytkownikowi '{permission_data.username}' do szlabanu '{permission_data.barrier_id}'.")
    user = db.get_user_by_username(permission_data.username)
    if not user:
        log.warning(f"Admin: Próba nadania uprawnień nieistniejącemu użytkownikowi: '{permission_data.username}'")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"User '{permission_data.username}' not found.")

    permission_id, status_msg = db.grant_db_permission(user['id'], permission_data.barrier_id,
                                                       permission_data.permission_level)

    if status_msg == "ok" and permission_id is not None:
        log.info(
            f"Admin: Nadano uprawnienie '{permission_data.permission_level}' użytkownikowi '{permission_data.username}' do szlabanu '{permission_data.barrier_id}'.")
        return models.PermissionResponse(
            id=permission_id,
            user_id=user['id'],
            username=permission_data.username,
            barrier_id=permission_data.barrier_id,
            permission_level=permission_data.permission_level
        )
    else:
        error_details = {
            "permission_exists": (status.HTTP_409_CONFLICT, "Permission already exists for this user and barrier."),
            "barrier_not_found": (status.HTTP_404_NOT_FOUND, f"Barrier with ID '{permission_data.barrier_id}' not found."),
            "user_not_found": (status.HTTP_404_NOT_FOUND, f"User '{permission_data.username}' not found (consistency issue?)."),
            "consistency_error": (status.HTTP_500_INTERNAL_SERVER_ERROR, "Database consistency error granting permission."),
            "db_error": (status.HTTP_500_INTERNAL_SERVER_ERROR, "Database error granting permission.")
        }
        status_code, detail_msg = error_details.get(status_msg, (status.HTTP_500_INTERNAL_SERVER_ERROR, "Unknown error granting permission."))
        log.error(f"Admin: Nieudane nadanie uprawnień: {detail_msg} (User: {permission_data.username}, Barrier: {permission_data.barrier_id}, Status: {status_msg})")
        raise HTTPException(status_code=status_code, detail=detail_msg)


# == Grupa: Remotes (Piloty - Wymaga Tokena Admina) ==
@app.post("/api/remotes", response_model=models.RemoteConfigResponse, status_code=status.HTTP_201_CREATED,
          tags=["Admin"], dependencies=[Depends(core.verify_admin_token)])
async def create_remote_endpoint(remote_data: models.RemoteCreate):
    """
    (Admin) Tworzy nowy pilot dla użytkownika do obsługi określonego szlabanu.
    Zwraca pełne dane konfiguracyjne pilota, łącznie z kluczami kryptograficznymi.
    """
    log.info(f"Admin: Żądanie utworzenia pilota '{remote_data.name}' dla użytkownika ID={remote_data.user_id} i szlabanu '{remote_data.barrier_id}'.")
    result = db.create_db_remote(remote_data.name, remote_data.user_id, remote_data.barrier_id)
    if not result:
        log.error(f"Admin: Nieudane tworzenie pilota '{remote_data.name}'. Sprawdź, czy użytkownik (ID={remote_data.user_id}) i szlaban ('{remote_data.barrier_id}') istnieją oraz czy użytkownik ma uprawnienia.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Failed to create remote. Check if user and barrier exist and user has permission for this barrier.")

    remote_id_db, remote_config_data = result
    log.info(f"Admin: Utworzono pilota '{remote_data.name}' (DB ID: {remote_id_db}, Remote ID: {remote_config_data.get('remote_id')}).")
    # Zwróć dane pilota jako odpowiedź
    return models.RemoteConfigResponse(**remote_config_data)


@app.get("/api/remotes/{remote_id}/config.c",
         tags=["Admin"], dependencies=[Depends(core.verify_admin_token)])
async def get_remote_config_c_endpoint(remote_id: str):
    """
    (Admin) Generuje plik konfiguracyjny C (config.c) dla pilota i umożliwia jego pobranie.
    """
    log.info(f"Admin: Żądanie pliku config.c dla pilota o ID (hex): '{remote_id}'.")
    remote = db.get_remote_by_id(remote_id) # get_remote_by_id oczekuje ID heksadecymalnego pilota
    if not remote:
        log.warning(f"Admin: Nie znaleziono pilota o ID (hex) '{remote_id}' do wygenerowania config.c.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Remote with ID '{remote_id}' not found.")

    try:
        config_content = config_generator.generate_config_c(remote)
        log.debug(f"Admin: Wygenerowano config.c dla pilota '{remote_id}'.")
        return Response(
            content=config_content,
            media_type="text/plain", # Lub "text/x-c"
            headers={"Content-Disposition": f"attachment; filename=config_{remote_id}.c"} # Sugerowana nazwa pliku
        )
    except Exception as e:
        log.exception(f"Admin: Błąd podczas generowania config.c dla pilota '{remote_id}': {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Error generating config file: {str(e)}")


@app.get("/api/remotes/{remote_id}/config.h",
         tags=["Admin"], dependencies=[Depends(core.verify_admin_token)])
async def get_remote_config_h_endpoint(remote_id: str):
    """
    (Admin) Generuje plik nagłówkowy config.h dla pilota i umożliwia jego pobranie.
    """
    log.info(f"Admin: Żądanie pliku config.h dla pilota o ID (hex): '{remote_id}'.")
    # Sprawdź tylko, czy pilot istnieje
    remote = db.get_remote_by_id(remote_id)
    if not remote:
        log.warning(f"Admin: Nie znaleziono pilota o ID (hex) '{remote_id}' do wygenerowania config.h.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Remote with ID '{remote_id}' not found.")

    try:
        # Zakładamy, że config.h jest generyczny i nie zależy od konkretnego pilota
        config_content = config_generator.generate_config_h()
        log.debug(f"Admin: Wygenerowano config.h (dla pilota '{remote_id}').")
        return Response(
            content=config_content,
            media_type="text/plain", # Lub "text/x-h"
            headers={"Content-Disposition": f"attachment; filename=config.h"}
        )
    except Exception as e:
        log.exception(f"Admin: Błąd podczas generowania config.h (dla pilota '{remote_id}'): {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Error generating header file: {str(e)}")

@app.delete("/api/remotes/{remote_id}", status_code=status.HTTP_204_NO_CONTENT,
            tags=["Admin"], dependencies=[Depends(core.verify_admin_token)])
async def delete_remote_endpoint(remote_id: str):
    """
    (Admin) Usuwa pilot z systemu na podstawie jego ID (hex).
    """
    log.info(f"Admin: Żądanie usunięcia pilota o ID (hex): '{remote_id}'.")
    success = db.delete_remote(remote_id) # delete_remote oczekuje ID heksadecymalnego pilota
    if not success:
        log.warning(f"Admin: Nie znaleziono pilota o ID (hex) '{remote_id}' do usunięcia lub wystąpił błąd.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Remote with ID '{remote_id}' not found or could not be deleted.")
    log.info(f"Admin: Pomyślnie usunięto pilota o ID (hex): '{remote_id}'.")
    # 204 No Content nie zwraca ciała odpowiedzi
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/users/{user_id}/remotes", response_model=List[models.RemoteResponse],
         tags=["Admin"], dependencies=[Depends(core.verify_admin_token)])
async def get_user_remotes_endpoint(user_id: int):
    """
    (Admin) Pobiera listę pilotów przypisanych do użytkownika.
    """
    log.info(f"Admin: Żądanie listy pilotów dla użytkownika o ID: {user_id}.")
    # Sprawdź czy użytkownik istnieje
    user = db.get_user_by_id(user_id) # Używamy nowej funkcji get_user_by_id
    if not user:
        log.warning(f"Admin: Nie znaleziono użytkownika o ID {user_id} przy pobieraniu jego pilotów.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"User with ID {user_id} not found.")

    remotes = db.get_user_remotes(user_id)
    log.debug(f"Admin: Znaleziono {len(remotes)} pilotów dla użytkownika ID={user_id}.")
    # Konwertuj dane z bazy na model odpowiedzi Pydantic
    response_list = [
        models.RemoteResponse(
            id=remote["id"],
            name=remote["name"],
            user_id=remote["user_id"],
            barrier_id=remote["barrier_id"],
            remote_id=remote["remote_id"],
            created_at=remote["created_at"],
            last_counter=remote["last_counter"]
        ) for remote in remotes
    ]
    return response_list


# == Grupa: Remote Verification (Publiczny Endpoint dla Szlabanów) ==
@app.post("/api/verify/remote", response_model=models.RemoteVerifyResponse, tags=["Remote Verification"])
async def verify_remote_endpoint(verify_data: models.RemoteVerifyRequest, request: Request):
    """
    Endpoint publiczny do weryfikacji pilota przez kontroler szlabanu.
    Weryfikuje, czy dany pilot ma dostęp do określonego szlabanu na podstawie
    zaszyfrowanej wiadomości (AES-CTR + HMAC-SHA256).
    """
    client_ip = request.client.host if request.client else "N/A"
    log.info(f"Żądanie weryfikacji pilota od {client_ip} dla szlabanu '{verify_data.barrier_id}'")
    log.debug(f"Dane zaszyfrowane (początek): '{verify_data.encrypted_data[:32]}...'") # Loguj tylko początek

    # --- KROK 1: Znajdź wszystkich potencjalnych pilotów dla tego szlabanu ---
    conn = None
    potential_remotes = []
    try:
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT id, remote_id, name, user_id, barrier_id, aes_key, hmac_key, iv, last_counter
            FROM {config.TABLE_REMOTES}
            WHERE barrier_id = ?
        """, (verify_data.barrier_id,))
        potential_remotes = cursor.fetchall()

    except sqlite3.Error as e:
        log.error(f"Błąd DB przy pobieraniu pilotów dla szlabanu '{verify_data.barrier_id}': {e}", exc_info=True)
        if conn: conn.close()
        # Zwróć odpowiedź zgodną z modelem, wskazując błąd serwera
        return models.RemoteVerifyResponse(access_granted=False, reason="server_db_error")
    finally:
        if conn: conn.close()

    if not potential_remotes:
        log.warning(f"Brak skonfigurowanych pilotów dla szlabanu '{verify_data.barrier_id}'. Weryfikacja niemożliwa.")
        return models.RemoteVerifyResponse(access_granted=False, reason="no_remotes_for_barrier")

    log.info(f"Znaleziono {len(potential_remotes)} potencjalnych pilotów dla szlabanu '{verify_data.barrier_id}'. Rozpoczynanie weryfikacji...")

    verified_remote = None
    received_counter = None
    verification_error_reason = "remote_not_found_or_invalid" # Domyślny błąd

    # --- KROK 2: Iteruj przez potencjalne piloty i próbuj zweryfikować wiadomość ---
    for remote_row in potential_remotes:
        remote_dict = dict(remote_row) # Upewnij się, że masz słownik
        log.debug(f"Próba weryfikacji używając pilota: ID={remote_dict['id']}, Name='{remote_dict['name']}', RemoteID(hex)='{remote_dict['remote_id']}'")

        try:
            valid, counter, error_msg = crypto_utils.verify_remote_message_ctr(
                verify_data.encrypted_data,
                remote_dict
            )

            if valid:
                log.info(f"Weryfikacja UDANA dla pilota ID={remote_dict['id']} (RemoteID hex: {remote_dict['remote_id']}). Otrzymany licznik: {counter}")
                verified_remote = remote_dict
                received_counter = counter
                break # Znaleziono pasującego pilota, przerwij pętlę
            else:
                # Logowanie nieudanej próby dla konkretnego pilota
                log.debug(f"Weryfikacja nieudana dla pilota ID={remote_dict['id']}. Powód: {error_msg}")
                if error_msg: # Zachowaj ostatni konkretny błąd
                    verification_error_reason = error_msg

        except Exception as e:
            # Błąd podczas samego procesu weryfikacji (np. w crypto_utils)
            log.error(f"Wyjątek podczas próby weryfikacji dla pilota ID={remote_dict['id']}: {e}", exc_info=True)
            verification_error_reason = "verification_internal_error"
            # Kontynuuj pętlę, może inny pilot zadziała

    # --- KROK 3: Przetwarzanie wyniku weryfikacji ---
    if verified_remote and received_counter is not None:
        # Weryfikacja powiodła się dla jednego z pilotów
        last_recorded_counter = verified_remote['last_counter']
        log.info(f"Porównanie liczników dla pilota ID={verified_remote['id']}: otrzymany={received_counter}, ostatni zapisany={last_recorded_counter}")

        # Sprawdź licznik (anty-replay attack)
        if received_counter <= last_recorded_counter:
            log.warning(f"Niepoprawny licznik dla pilota ID={verified_remote['id']}: otrzymano {received_counter}, ostatni zapisany {last_recorded_counter}. Możliwy atak replay.")
            # Zapisz zdarzenie nieudanej weryfikacji
            event_data_fail = models.BarrierEventDBInput(
                barrier_id=verify_data.barrier_id, event_type="remote_access", trigger_method="remote",
                timestamp=datetime.now().isoformat(), user_id=str(verified_remote['user_id']), success=False,
                details=f"Remote ID: {verified_remote['remote_id']}, Invalid counter (rcv: {received_counter}, last: {last_recorded_counter})",
                failed_action="invalid_counter"
            )
            db.add_event_to_db(event_data_fail, datetime.now().isoformat())
            return models.RemoteVerifyResponse(access_granted=False, reason="invalid_counter")

        # Licznik jest poprawny, aktualizuj go w bazie
        log.info(f"Licznik poprawny. Aktualizacja licznika dla pilota ID={verified_remote['id']} (RemoteID hex: {verified_remote['remote_id']}) do {received_counter}")
        update_success = db.update_remote_counter(verified_remote['remote_id'], received_counter)

        if not update_success:
            log.error(f"Nie udało się zaktualizować licznika dla pilota ID={verified_remote['id']} (RemoteID hex: {verified_remote['remote_id']}) w bazie danych!")
            # Weryfikacja krypto się udała, ale nie zapisano stanu - to błąd serwera
            return models.RemoteVerifyResponse(access_granted=False, reason="server_db_update_error")

        # Licznik zaktualizowany, dostęp przyznany. Zapisz zdarzenie sukcesu.
        event_data_ok = models.BarrierEventDBInput(
            barrier_id=verify_data.barrier_id, event_type="remote_access", trigger_method="remote",
            timestamp=datetime.now().isoformat(), user_id=str(verified_remote['user_id']), success=True,
            details=f"Remote ID: {verified_remote['remote_id']}, Access granted, Counter: {received_counter}",
            failed_action=None
        )
        db.add_event_to_db(event_data_ok, datetime.now().isoformat())

        log.info(f"Dostęp PRZYZNANY dla szlabanu '{verify_data.barrier_id}' przez pilota ID={verified_remote['id']} (RemoteID hex: {verified_remote['remote_id']})")
        return models.RemoteVerifyResponse(access_granted=True, reason="verified") # Dodano reason dla sukcesu

    else:
        # Żaden pilot nie zweryfikował wiadomości poprawnie
        log.warning(f"Weryfikacja nieudana dla wszystkich potencjalnych pilotów dla szlabanu '{verify_data.barrier_id}'. Ostateczny powód: {verification_error_reason}")
        # Zapisz ogólne zdarzenie nieudanej próby dostępu
        event_data_final_fail = models.BarrierEventDBInput(
            barrier_id=verify_data.barrier_id, event_type="remote_access", trigger_method="remote",
            timestamp=datetime.now().isoformat(), user_id=None, success=False,
            details=f"Encrypted data received, but failed verification. Final reason: {verification_error_reason}",
            failed_action=verification_error_reason
        )
        db.add_event_to_db(event_data_final_fail, datetime.now().isoformat())

        return models.RemoteVerifyResponse(access_granted=False, reason=verification_error_reason)


# == Grupa: User Actions (Akcje Użytkownika - Wymaga Basic Auth) ==
@app.post("/api/barriers/{barrier_id}/open",
          status_code=status.HTTP_202_ACCEPTED, # Centrala akceptuje żądanie i przekazuje dalej
          tags=["User Actions"],
          summary="Otwiera wskazany szlaban")
async def open_barrier_endpoint(barrier_id: str, current_user: sqlite3.Row = Depends(core.get_current_user)):
    """
    (User) Wysyła komendę 'open' do wskazanego szlabanu po weryfikacji uprawnień.
    Centrala zwraca 202 Accepted, ale *ciało odpowiedzi* w przypadku sukcesu lub błędu
    pochodzi bezpośrednio od kontrolera szlabanu (przekazane przez HTTPException w send_command_to_barrier).
    """
    log.info(f"User '{current_user['username']}': Żądanie otwarcia szlabanu '{barrier_id}'.")
    # send_command_to_barrier obsługuje logowanie, sprawdzanie uprawnień, wysyłkę i obsługę odpowiedzi/błędów
    await core.send_command_to_barrier(barrier_id, "open", current_user)
    # Jeśli send_command_to_barrier nie rzuci wyjątku (co nie powinno się zdarzyć przy poprawnej implementacji),
    # można by tu zwrócić domyślną odpowiedź, ale polegamy na tym, że zawsze rzuci HTTPException.


@app.post("/api/barriers/{barrier_id}/close", status_code=status.HTTP_202_ACCEPTED, tags=["User Actions"],
          summary="Zamyka wskazany szlaban")
async def close_barrier_endpoint(barrier_id: str, current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Wysyła komendę 'close' do wskazanego szlabanu. Działa analogicznie do /open."""
    log.info(f"User '{current_user['username']}': Żądanie zamknięcia szlabanu '{barrier_id}'.")
    await core.send_command_to_barrier(barrier_id, "close", current_user)


@app.post("/api/barriers/{barrier_id}/service/start", status_code=status.HTTP_202_ACCEPTED, tags=["User Actions"],
          summary="Włącza tryb serwisowy dla szlabanu")
async def service_start_endpoint(barrier_id: str, current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Wysyła komendę 'service/start' (wymaga uprawnień 'technician'). Działa analogicznie do /open."""
    log.info(f"User '{current_user['username']}': Żądanie włączenia trybu serwisowego dla szlabanu '{barrier_id}'.")
    await core.send_command_to_barrier(barrier_id, "service/start", current_user)


@app.post("/api/barriers/{barrier_id}/service/end", status_code=status.HTTP_202_ACCEPTED, tags=["User Actions"],
          summary="Wyłącza tryb serwisowy dla szlabanu")
async def service_end_endpoint(barrier_id: str, current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Wysyła komendę 'service/end' (wymaga uprawnień 'technician'). Działa analogicznie do /open."""
    log.info(f"User '{current_user['username']}': Żądanie wyłączenia trybu serwisowego dla szlabanu '{barrier_id}'.")
    await core.send_command_to_barrier(barrier_id, "service/end", current_user)


# == Grupa: User Info (Informacje dla Zalogowanego Użytkownika - Wymaga Basic Auth) ==
@app.get("/api/my/barriers", response_model=List[models.MyBarrierResponse], tags=["User Info"])
async def get_my_barriers_endpoint(current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Zwraca listę szlabanów, do których zalogowany użytkownik ma dostęp wraz z poziomem uprawnień."""
    user_id = current_user['id']
    username = current_user['username']
    log.info(f"User '{username}': Żądanie listy autoryzowanych szlabanów.")
    barriers_details = db.get_user_authorized_barriers_details(user_id)
    if barriers_details is None:
        log.error(f"User '{username}': Błąd pobierania listy autoryzowanych szlabanów z bazy danych.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error fetching authorized barriers.")
    log.debug(f"User '{username}': Znaleziono {len(barriers_details)} autoryzowanych szlabanów.")
    return barriers_details


@app.get("/api/my/remotes", response_model=List[models.RemoteResponse], tags=["User Info"])
async def get_my_remotes_endpoint(current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Pobiera listę pilotów przypisanych do zalogowanego użytkownika."""
    user_id = current_user['id']
    username = current_user['username']
    log.info(f"User '{username}': Żądanie listy przypisanych pilotów.")
    remotes = db.get_user_remotes(user_id)
    if remotes is None: # Zakładamy, że get_user_remotes zwraca None w przypadku błędu DB
        log.error(f"User '{username}': Błąd pobierania listy pilotów z bazy danych.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error fetching user remotes.")

    log.debug(f"User '{username}': Znaleziono {len(remotes)} pilotów.")
    response_list = [
        models.RemoteResponse(
            id=remote["id"], name=remote["name"], user_id=remote["user_id"],
            barrier_id=remote["barrier_id"], remote_id=remote["remote_id"],
            created_at=remote["created_at"], last_counter=remote["last_counter"]
        ) for remote in remotes
    ]
    return response_list


@app.get("/api/my/events", response_model=List[models.BarrierEventDBResponse], tags=["User Info"])
async def get_my_events_endpoint(limit: int = config.DEFAULT_EVENT_LIMIT,
                                 current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Zwraca ostatnie zdarzenia z autoryzowanych szlabanów."""
    user_id = current_user['id']
    username = current_user['username']
    log.info(f"User '{username}': Żądanie ostatnich {limit} zdarzeń z autoryzowanych szlabanów.")
    authorized_ids = db.get_user_authorized_barrier_ids(user_id)
    if authorized_ids is None: # Błąd pobierania ID
         log.error(f"User '{username}': Błąd pobierania autoryzowanych ID szlabanów.")
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching authorized barrier IDs.")
    if not authorized_ids:
        log.debug(f"User '{username}': Brak autoryzowanych szlabanów.")
        return []

    log.debug(f"User '{username}': Autoryzowane szlabany: {authorized_ids}. Pobieranie zdarzeń...")
    events = db.get_events_from_db(barrier_ids=authorized_ids, limit=limit)
    if events is None:
        log.error(f"User '{username}': Błąd pobierania zdarzeń z bazy danych.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Error reading events from database.")
    log.debug(f"User '{username}': Zwrócono {len(events)} zdarzeń.")
    return events


@app.get("/api/barriers/{barrier_id}/events", response_model=List[models.BarrierEventDBResponse], tags=["User Info"])
async def get_specific_barrier_events_endpoint(barrier_id: str, limit: int = config.DEFAULT_EVENT_LIMIT,
                                               current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Zwraca ostatnie zdarzenia dla konkretnego, autoryzowanego szlabanu."""
    user_id = current_user['id']
    username = current_user['username']
    log.info(f"User '{username}': Żądanie ostatnich {limit} zdarzeń dla szlabanu '{barrier_id}'.")

    # Sprawdź uprawnienia
    permission = db.get_db_permission_level(user_id, barrier_id)
    if permission is None:
        log.warning(f"User '{username}': Odmowa dostępu do zdarzeń szlabanu '{barrier_id}' - brak uprawnień.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"No permission for barrier '{barrier_id}'.")

    # Pobierz zdarzenia
    log.debug(f"User '{username}': Ma uprawnienia '{permission}' do szlabanu '{barrier_id}'. Pobieranie zdarzeń...")
    events = db.get_events_from_db(barrier_ids=[barrier_id], limit=limit)
    if events is None:
        log.error(f"User '{username}': Błąd pobierania zdarzeń dla szlabanu '{barrier_id}' z bazy danych.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Error reading events from database.")
    log.debug(f"User '{username}': Zwrócono {len(events)} zdarzeń dla szlabanu '{barrier_id}'.")
    return events


@app.get("/api/my/failures", response_model=List[models.BarrierEventDBResponse], tags=["User Info"])
async def get_my_failures_endpoint(limit: int = config.DEFAULT_EVENT_LIMIT,
                                   current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Zwraca ostatnie awarie (zdarzenia z success=false) z autoryzowanych szlabanów."""
    user_id = current_user['id']
    username = current_user['username']
    log.info(f"User '{username}': Żądanie ostatnich {limit} awarii z autoryzowanych szlabanów.")
    authorized_ids = db.get_user_authorized_barrier_ids(user_id)
    if authorized_ids is None:
         log.error(f"User '{username}': Błąd pobierania autoryzowanych ID szlabanów przy szukaniu awarii.")
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching authorized barrier IDs.")
    if not authorized_ids:
        log.debug(f"User '{username}': Brak autoryzowanych szlabanów do sprawdzenia awarii.")
        return []

    log.debug(f"User '{username}': Autoryzowane szlabany: {authorized_ids}. Pobieranie awarii...")
    failure_events = db.get_events_from_db(barrier_ids=authorized_ids, limit=limit, only_failures=True)
    if failure_events is None:
        log.error(f"User '{username}': Błąd pobierania awarii z bazy danych.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Error reading failure events from database.")
    log.debug(f"User '{username}': Zwrócono {len(failure_events)} awarii.")
    return failure_events

# == Endpoint Powitalny / Statusowy ==
@app.get("/", tags=["Status"])
async def root():
    """Zwraca podstawowe informacje o statusie API."""
    log.info("Żądanie statusu API (endpoint '/')")
    return {
        "message": "Witaj w API Centrali ESZP!",
        "version": app.version,
        "status": "operational",
        "timestamp": datetime.now().isoformat()
        }

# --- Uruchomienie Serwera (tylko dla deweloperki) ---
if __name__ == "__main__":
    log.info("Uruchamianie serwera Uvicorn bezpośrednio (tylko dla celów deweloperskich)...")
    uvicorn.run(
        "main:app",
        host=config.API_HOST, # Użyj konfiguracji hosta
        port=config.API_PORT, # Użyj konfiguracji portu
        reload=True, # Włącz automatyczne przeładowanie dla deweloperki
        log_level=config.LOG_LEVEL.lower() # Przekaż poziom logowania do uvicorna
        )