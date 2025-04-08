#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
import sqlite3  # Wciąż potrzebne dla type hint w zależnościach
from datetime import datetime
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status, Depends

# Importuj z nowych plików
import config
import crypto_utils
import models  # Importuje wszystkie modele
import db  # Importuje wszystkie funkcje DB
import core  # Importuje funkcje core/security/dependencies
import config_generator  # Importuje generator plików konfiguracyjnych

# --- Konfiguracja Logowania ---
logging.basicConfig(level=config.LOG_LEVEL, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
log = logging.getLogger(__name__)
# Zmniejszamy gadatliwość logów dostępowych uvicorna (opcjonalnie)
logging.getLogger('uvicorn.access').setLevel(logging.WARNING)


# --- Lifespan FastAPI ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Server startup...")
    db.init_db()  # Uruchom inicjalizację bazy przy starcie
    yield
    log.info("Server shutdown...")


# --- Aplikacja FastAPI ---
app = FastAPI(
    title="Centrala ESZP v1.4 (Remotes Extension)",
    description="API do zarządzania i kontroli szlabanów oraz pilotów.",
    version="1.4.0",  # Zwiększona wersja po dodaniu obsługi pilotów
    lifespan=lifespan
)


# --- Endpointy API ---

# == Grupa: Events ==
@app.post("/barrier/event", status_code=status.HTTP_200_OK, tags=["Events"])
async def receive_barrier_event_endpoint(event_data: models.BarrierEventDBInput):
    """Odbiera zdarzenie od kontrolera szlabanu i zapisuje do bazy."""
    received_time = datetime.now().isoformat()
    if db.add_event_to_db(event_data, received_time):
        return {"status": "received_ok", "received_at": received_time}
    else:
        # Logowanie błędu odbywa się w db.add_event_to_db
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save event data.")


# == Grupa: Admin ==
@app.get("/api/events", response_model=List[models.BarrierEventDBResponse], tags=["Admin"],
         dependencies=[Depends(core.verify_admin_token)])
async def get_all_events_endpoint(limit: int = config.DEFAULT_EVENT_LIMIT):
    """(Admin) Pobiera ostatnie zdarzenia ze WSZYSTKICH szlabanów."""
    events = db.get_events_from_db(barrier_ids=None, limit=limit, only_failures=False)
    if events is None:  # get_events_from_db zwraca None w przypadku błędu DB
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to retrieve events from database.")
    # FastAPI automatycznie zwaliduje i przekonwertuje listę dict na listę BarrierEventDBResponse
    return events


@app.post("/api/users", response_model=models.UserResponse, status_code=status.HTTP_201_CREATED, tags=["Admin"],
          dependencies=[Depends(core.verify_admin_token)])
async def create_user_endpoint(user_data: models.UserCreate):
    """(Admin) Tworzy nowego użytkownika."""
    # Sprawdź, czy użytkownik już istnieje
    existing_user = db.get_user_by_username(user_data.username)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Username '{user_data.username}' already exists.")

    # Stwórz hash hasła
    hashed_password = core.get_password_hash(user_data.password)

    # Dodaj użytkownika do bazy
    user_id = db.create_db_user(user_data.username, hashed_password)
    if user_id:
        log.info(f"Admin created user '{user_data.username}' (ID: {user_id}).")
        return models.UserResponse(id=user_id, username=user_data.username)
    else:
        # Błąd został zalogowany w create_db_user
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error creating user.")


@app.post("/api/barriers", response_model=models.BarrierResponse, status_code=status.HTTP_201_CREATED, tags=["Admin"],
          dependencies=[Depends(core.verify_admin_token)])
async def add_barrier_endpoint(barrier_data: models.BarrierCreate):
    """(Admin) Dodaje nowy szlaban (rejestruje jego ID i URL)."""
    # Prosta walidacja URL
    if not barrier_data.controller_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid controller_url format (must start with http:// or https://).")

    # Dodaj szlaban do bazy
    db_id = db.create_db_barrier(barrier_data.barrier_id, barrier_data.controller_url)
    if db_id:
        log.info(f"Admin added barrier '{barrier_data.barrier_id}'.")
        return models.BarrierResponse(id=db_id, **barrier_data.model_dump())
    else:
        # create_db_barrier zwrócił None, co oznacza, że ID lub URL już istnieje (lub inny błąd DB)
        # Sprawdźmy co było przyczyną dla lepszego komunikatu błędu (choć to race condition)
        conn_check = db.get_db()
        cursor_check = conn_check.cursor()
        cursor_check.execute(f"SELECT 1 FROM {config.TABLE_BARRIERS} WHERE barrier_id=? OR controller_url=?",
                             (barrier_data.barrier_id, barrier_data.controller_url))
        exists = cursor_check.fetchone()
        conn_check.close()
        if exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="Barrier ID or Controller URL already exists.")
        else:  # Jeśli nie istnieje, a był błąd, to coś innego poszło nie tak
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Database error adding barrier.")


@app.post("/api/permissions", response_model=models.PermissionResponse, status_code=status.HTTP_201_CREATED,
          tags=["Admin"], dependencies=[Depends(core.verify_admin_token)])
async def grant_permission_endpoint(permission_data: models.PermissionCreate):
    """(Admin) Nadaje użytkownikowi uprawnienia do szlabanu."""
    # Znajdź użytkownika
    user = db.get_user_by_username(permission_data.username)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"User '{permission_data.username}' not found.")

    # Nadaj uprawnienie
    permission_id, status_msg = db.grant_db_permission(user['id'], permission_data.barrier_id,
                                                       permission_data.permission_level)

    if status_msg == "ok" and permission_id is not None:
        log.info(
            f"Admin granted '{permission_data.permission_level}' permission to user '{permission_data.username}' for barrier '{permission_data.barrier_id}'.")
        return models.PermissionResponse(
            id=permission_id,
            user_id=user['id'],
            username=permission_data.username,  # Lub user['username']
            barrier_id=permission_data.barrier_id,
            permission_level=permission_data.permission_level
        )
    else:
        # Mapowanie kodu błędu z funkcji DB na status HTTP i komunikat
        error_details = {
            "permission_exists": (status.HTTP_409_CONFLICT, "Permission already exists for this user and barrier."),
            "barrier_not_found": (
            status.HTTP_404_NOT_FOUND, f"Barrier with ID '{permission_data.barrier_id}' not found."),
            "user_not_found": (
            status.HTTP_404_NOT_FOUND, f"User '{permission_data.username}' not found (consistency issue?)."),
            # Powinno być wykryte wcześniej
            "consistency_error": (
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Database consistency error granting permission."),
            "db_error": (status.HTTP_500_INTERNAL_SERVER_ERROR, "Database error granting permission.")
        }
        status_code, detail_msg = error_details.get(status_msg, (
        status.HTTP_500_INTERNAL_SERVER_ERROR, "Unknown error granting permission."))
        log.warning(
            f"Failed to grant permission: {detail_msg} (User: {permission_data.username}, Barrier: {permission_data.barrier_id}, Status: {status_msg})")
        raise HTTPException(status_code=status_code, detail=detail_msg)


# == Grupa: Remotes (Piloty) ==
@app.post("/api/remotes", response_model=models.RemoteConfigResponse, status_code=status.HTTP_201_CREATED,
          tags=["Admin"], dependencies=[Depends(core.verify_admin_token)])
async def create_remote_endpoint(remote_data: models.RemoteCreate):
    """
    (Admin) Tworzy nowy pilot dla użytkownika do obsługi określonego szlabanu.
    Zwraca pełne dane konfiguracyjne pilota, łącznie z kluczami kryptograficznymi.
    """
    # Użyj funkcji db.create_db_remote do utworzenia pilota
    result = db.create_db_remote(remote_data.name, remote_data.user_id, remote_data.barrier_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Failed to create remote. Check if user and barrier exist and user has permission for this barrier.")

    remote_id, remote_data = result

    # Zwróć dane pilota jako odpowiedź
    return models.RemoteConfigResponse(**remote_data)


from fastapi.responses import Response


@app.get("/api/remotes/{remote_id}/config.c",
         tags=["Admin"], dependencies=[Depends(core.verify_admin_token)])
async def get_remote_config_c_endpoint(remote_id: str):
    """
    (Admin) Generuje plik konfiguracyjny C dla pilota i umożliwia jego pobranie.
    """
    # Pobierz dane pilota
    remote = db.get_remote_by_id(remote_id)
    if not remote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Remote with ID '{remote_id}' not found.")

    # Użyj generatora do wygenerowania pliku konfiguracyjnego
    try:
        config_content = config_generator.generate_config_c(remote)

        # Zwróć jako plik do pobrania
        return Response(
            content=config_content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename=config.c"
            }
        )
    except Exception as e:
        log.error(f"Failed to generate config.c for remote '{remote_id}': {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Error generating config file: {str(e)}")


@app.get("/api/remotes/{remote_id}/config.h",
         tags=["Admin"], dependencies=[Depends(core.verify_admin_token)])
async def get_remote_config_h_endpoint(remote_id: str):
    """
    (Admin) Generuje plik nagłówkowy config.h dla pilota i umożliwia jego pobranie.
    """
    # Pobierz dane pilota (tylko do walidacji istnienia)
    remote = db.get_remote_by_id(remote_id)
    if not remote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Remote with ID '{remote_id}' not found.")

    # Użyj generatora do wygenerowania pliku nagłówkowego
    try:
        config_content = config_generator.generate_config_h()

        # Zwróć jako plik do pobrania
        return Response(
            content=config_content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename=config.h"
            }
        )
    except Exception as e:
        log.error(f"Failed to generate config.h for remote '{remote_id}': {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Error generating header file: {str(e)}")

@app.delete("/api/remotes/{remote_id}", status_code=status.HTTP_204_NO_CONTENT,
            tags=["Admin"], dependencies=[Depends(core.verify_admin_token)])
async def delete_remote_endpoint(remote_id: str):
    """
    (Admin) Usuwa pilot z systemu.
    """
    success = db.delete_remote(remote_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Remote with ID '{remote_id}' not found or could not be deleted.")

    return None  # 204 No Content nie wymaga ciała odpowiedzi


@app.get("/api/users/{user_id}/remotes", response_model=List[models.RemoteResponse],
         tags=["Admin"], dependencies=[Depends(core.verify_admin_token)])
async def get_user_remotes_endpoint(user_id: int):
    """
    (Admin) Pobiera listę pilotów przypisanych do użytkownika.
    """
    # Sprawdź czy użytkownik istnieje
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {config.TABLE_USERS} WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"User with ID {user_id} not found.")

    # Pobierz piloty
    remotes = db.get_user_remotes(user_id)

    # Zamień na model odpowiedzi (bez kluczy kryptograficznych)
    return [models.RemoteResponse(
        id=remote["id"],
        name=remote["name"],
        user_id=remote["user_id"],
        barrier_id=remote["barrier_id"],
        remote_id=remote["remote_id"],
        created_at=remote["created_at"],
        last_counter=remote["last_counter"]  # Dodane brakujące pole
    ) for remote in remotes]


@app.post("/api/verify/remote", response_model=models.RemoteVerifyResponse, tags=["Remote Verification"])
async def verify_remote_endpoint(verify_data: models.RemoteVerifyRequest):
    """
    Endpoint publiczny do weryfikacji pilota przez kontroler szlabanu.
    Weryfikuje, czy dany pilot ma dostęp do określonego szlabanu na podstawie
    zaszyfrowanej wiadomości (AES-CTR + HMAC-SHA256).

    Wiadomość musi być poprawnie zaszyfrowana i podpisana kluczami
    przypisanymi do jednego z pilotów autoryzowanych dla tego szlabanu.
    """
    log.info(f"Remote verification request received for barrier '{verify_data.barrier_id}'")
    log.info(f"Encrypted data (hex): '{verify_data.encrypted_data}'")

    # --- KROK 1: Znajdź wszystkich potencjalnych pilotów dla tego szlabanu ---
    conn = None
    potential_remotes = []
    try:
        conn = db.get_db()
        cursor = conn.cursor()
        # Pobierz wszystkie piloty przypisane do danego szlabanu
        cursor.execute(f"""
            SELECT id, remote_id, name, user_id, barrier_id, aes_key, hmac_key, iv, last_counter
            FROM {config.TABLE_REMOTES}
            WHERE barrier_id = ?
        """, (verify_data.barrier_id,))
        potential_remotes = cursor.fetchall() # fetchall() zwraca listę słowników/krotek

    except sqlite3.Error as e:
        log.error(f"Database error fetching remotes for barrier '{verify_data.barrier_id}': {e}", exc_info=True)
        if conn:
            conn.close()
        # Zwracamy błąd serwera, bo nie mogliśmy nawet sprawdzić pilotów
        return models.RemoteVerifyResponse(access_granted=False, reason="server_db_error")
    finally:
        if conn:
            conn.close() # Zawsze zamykaj połączenie

    if not potential_remotes:
        log.warning(f"No remotes configured for barrier '{verify_data.barrier_id}'.")
        return models.RemoteVerifyResponse(access_granted=False, reason="no_remotes_for_barrier")

    log.info(f"Found {len(potential_remotes)} potential remotes for barrier '{verify_data.barrier_id}'. Trying verification...")

    verified_remote = None
    received_counter = None
    verification_error_reason = "remote_not_found_or_invalid" # Domyślny błąd jeśli pętla nic nie znajdzie

    # --- KROK 2: Iteruj przez potencjalne piloty i próbuj zweryfikować wiadomość ---
    for remote_row in potential_remotes:
        # Konwertuj wiersz bazy danych (krotkę/Row) na słownik, jeśli nie jest
        # (Zakładając, że db.get_db() ma ustawiony row_factory na sqlite3.Row)
        remote_dict = dict(remote_row)
        log.debug(f"Attempting verification using remote: ID={remote_dict['id']}, Name='{remote_dict['name']}', RemoteID(hex)='{remote_dict['remote_id']}'")

        try:
            # Użyj nowej funkcji weryfikującej z crypto_utils
            valid, counter, error_msg = crypto_utils.verify_remote_message_ctr(
                verify_data.encrypted_data,
                remote_dict # Przekaż cały słownik z danymi pilota
            )

            if valid:
                # Znaleźliśmy pasującego pilota i wiadomość jest poprawna!
                log.info(f"Verification SUCCESSFUL for remote ID {remote_dict['id']} (RemoteID hex: {remote_dict['remote_id']}). Received counter: {counter}")
                verified_remote = remote_dict
                received_counter = counter
                break # Przerywamy pętlę, bo znaleźliśmy właściwego pilota
            else:
                # Weryfikacja nie powiodła się dla tego pilota, logujemy powód i próbujemy dalej
                log.debug(f"Verification failed for remote ID {remote_dict['id']}. Reason: {error_msg}")
                # Zachowajmy ostatni błąd, na wypadek gdyby żaden pilot nie pasował
                if error_msg:
                    verification_error_reason = error_msg

        except Exception as e:
            # Błąd podczas samego procesu weryfikacji dla danego pilota
            log.error(f"Exception during verification attempt for remote ID {remote_dict['id']}: {e}", exc_info=True)
            # Możemy kontynuować pętlę, może inny pilot zadziała
            verification_error_reason = "verification_internal_error"


    # --- KROK 3: Przetwarzanie wyniku weryfikacji ---
    if verified_remote and received_counter is not None:
        # Weryfikacja powiodła się dla jednego z pilotów

        # Sprawdź licznik (anty-replay attack)
        last_recorded_counter = verified_remote['last_counter']
        log.info(f"Comparing counters: received={received_counter}, last_recorded={last_recorded_counter}")

        if received_counter <= last_recorded_counter:
            log.warning(f"Invalid counter for remote ID {verified_remote['id']}: received {received_counter}, last recorded {last_recorded_counter}. Possible replay attack.")
            # Zapisz zdarzenie nieudanej weryfikacji z powodu licznika
            event_data = models.BarrierEventDBInput(
                barrier_id=verify_data.barrier_id,
                event_type="remote_access",
                trigger_method="remote",
                timestamp=datetime.now().isoformat(),
                user_id=str(verified_remote['user_id']), # Użyj user_id z znalezionego pilota
                success=False,
                details=f"Remote ID: {verified_remote['remote_id']}, Invalid counter (rcv: {received_counter}, last: {last_recorded_counter})",
                failed_action="invalid_counter"
            )
            db.add_event_to_db(event_data, datetime.now().isoformat()) # Użyj nowej sygnatury funkcji db
            return models.RemoteVerifyResponse(access_granted=False, reason="invalid_counter")

        # Licznik jest poprawny, aktualizuj go w bazie
        log.info(f"Counter is valid. Updating counter for remote ID {verified_remote['id']} to {received_counter}")
        # Używamy remote_id (hex string) jako identyfikatora w funkcji update
        update_success = db.update_remote_counter(verified_remote['remote_id'], received_counter)

        if not update_success:
            log.error(f"Failed to update counter for remote ID {verified_remote['remote_id']} in the database!")
            # Mimo że weryfikacja się powiodła, nie mogliśmy zapisać nowego licznika.
            # To problematyczne. Zwracamy błąd serwera, ale można rozważyć inną strategię.
            return models.RemoteVerifyResponse(access_granted=False, reason="server_db_update_error")

        # Licznik zaktualizowany, dostęp przyznany. Zapisz zdarzenie sukcesu.
        event_data = models.BarrierEventDBInput(
            barrier_id=verify_data.barrier_id,
            event_type="remote_access",
            trigger_method="remote",
            timestamp=datetime.now().isoformat(),
            user_id=str(verified_remote['user_id']),
            success=True,
            details=f"Remote ID: {verified_remote['remote_id']}, Access granted, Counter: {received_counter}",
            failed_action=None
        )
        db.add_event_to_db(event_data, datetime.now().isoformat())

        log.info(f"Access GRANTED for barrier '{verify_data.barrier_id}' via remote ID {verified_remote['id']} (RemoteID hex: {verified_remote['remote_id']})")
        return models.RemoteVerifyResponse(access_granted=True)

    else:
        # Pętla zakończyła się, ale żaden pilot nie zweryfikował wiadomości poprawnie
        log.warning(f"Verification failed for all potential remotes for barrier '{verify_data.barrier_id}'. Final reason: {verification_error_reason}")
        # Zapisz ogólne zdarzenie nieudanej próby dostępu (bez przypisania do konkretnego użytkownika/pilota, bo nie wiemy który to był)
        event_data = models.BarrierEventDBInput(
            barrier_id=verify_data.barrier_id,
            event_type="remote_access",
            trigger_method="remote",
            timestamp=datetime.now().isoformat(),
            user_id=None, # Nie znamy użytkownika
            success=False,
            details=f"Encrypted data received, but failed verification. Reason: {verification_error_reason}",
            failed_action=verification_error_reason
        )
        db.add_event_to_db(event_data, datetime.now().isoformat())

        return models.RemoteVerifyResponse(access_granted=False, reason=verification_error_reason)
# == Grupa: User Actions ==
@app.post("/api/barriers/{barrier_id}/open",
          status_code=status.HTTP_202_ACCEPTED,
          tags=["User Actions"],
          summary="Otwiera wskazany szlaban")
async def open_barrier_endpoint(barrier_id: str, current_user: sqlite3.Row = Depends(core.get_current_user)):
    """
    (User) Wysyła komendę 'open' do wskazanego szlabanu.
    Centrala zwraca 202 Accepted, ale *ciało odpowiedzi* zawiera status i dane zwrócone przez kontroler szlabanu.
    W przypadku błędu komunikacji z kontrolerem, centrala zwróci odpowiedni błąd 5xx.
    """
    await core.send_command_to_barrier(barrier_id, "open", current_user)


@app.post("/api/barriers/{barrier_id}/close", status_code=status.HTTP_202_ACCEPTED, tags=["User Actions"],
          summary="Zamyka wskazany szlaban")
async def close_barrier_endpoint(barrier_id: str, current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Wysyła komendę 'close' do wskazanego szlabanu. Działa jak /open."""
    await core.send_command_to_barrier(barrier_id, "close", current_user)


@app.post("/api/barriers/{barrier_id}/service/start", status_code=status.HTTP_202_ACCEPTED, tags=["User Actions"],
          summary="Włącza tryb serwisowy")
async def service_start_endpoint(barrier_id: str, current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Wysyła komendę 'service/start' (wymaga 'technician'). Działa jak /open."""
    await core.send_command_to_barrier(barrier_id, "service/start", current_user)


@app.post("/api/barriers/{barrier_id}/service/end", status_code=status.HTTP_202_ACCEPTED, tags=["User Actions"],
          summary="Wyłącza tryb serwisowy")
async def service_end_endpoint(barrier_id: str, current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Wysyła komendę 'service/end' (wymaga 'technician'). Działa jak /open."""
    await core.send_command_to_barrier(barrier_id, "service/end", current_user)


# == Grupa: User Info ==
@app.get("/api/my/barriers", response_model=List[models.MyBarrierResponse], tags=["User Info"])
async def get_my_barriers_endpoint(current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Zwraca listę szlabanów, do których zalogowany użytkownik ma dostęp."""
    barriers_details = db.get_user_authorized_barriers_details(current_user['id'])
    return barriers_details


@app.get("/api/my/remotes", response_model=List[models.RemoteResponse], tags=["User Info"])
async def get_my_remotes_endpoint(current_user: sqlite3.Row = Depends(core.get_current_user)):
    """
    (User) Pobiera listę pilotów przypisanych do zalogowanego użytkownika.
    """
    remotes = db.get_user_remotes(current_user['id'])

    return [models.RemoteResponse(
        id=remote["id"],
        name=remote["name"],
        user_id=remote["user_id"],
        barrier_id=remote["barrier_id"],
        remote_id=remote["remote_id"],
        created_at=remote["created_at"],
        last_counter=remote["last_counter"]  # Dodane brakujące pole
    ) for remote in remotes]


@app.get("/api/my/events", response_model=List[models.BarrierEventDBResponse], tags=["User Info"])
async def get_my_events_endpoint(limit: int = config.DEFAULT_EVENT_LIMIT,
                                 current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Zwraca ostatnie zdarzenia z autoryzowanych szlabanów."""
    authorized_ids = db.get_user_authorized_barrier_ids(current_user['id'])
    if not authorized_ids:
        return []  # Użytkownik nie ma dostępu do żadnych szlabanów

    events = db.get_events_from_db(barrier_ids=authorized_ids, limit=limit)
    if events is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Error reading events from database.")
    return events


@app.get("/api/barriers/{barrier_id}/events", response_model=List[models.BarrierEventDBResponse], tags=["User Info"])
async def get_specific_barrier_events_endpoint(barrier_id: str, limit: int = config.DEFAULT_EVENT_LIMIT,
                                               current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Zwraca ostatnie zdarzenia dla konkretnego, autoryzowanego szlabanu."""
    # Sprawdź uprawnienia do tego konkretnego szlabanu
    permission = db.get_db_permission_level(current_user['id'], barrier_id)
    if permission is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"No permission for barrier '{barrier_id}'.")

    # Pobierz zdarzenia tylko dla tego szlabanu
    events = db.get_events_from_db(barrier_ids=[barrier_id], limit=limit)
    if events is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Error reading events from database.")
    return events


@app.get("/api/my/failures", response_model=List[models.BarrierEventDBResponse], tags=["User Info"])
async def get_my_failures_endpoint(limit: int = config.DEFAULT_EVENT_LIMIT,
                                   current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Zwraca ostatnie awarie (zdarzenia z success=false) z autoryzowanych szlabanów."""
    authorized_ids = db.get_user_authorized_barrier_ids(current_user['id'])
    if not authorized_ids:
        return []

    failure_events = db.get_events_from_db(barrier_ids=authorized_ids, limit=limit, only_failures=True)
    if failure_events is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Error reading failure events from database.")
    return failure_events


if __name__ == "__main__":
    import uvicorn

    log.info("Starting Uvicorn server directly (for development only)...")
    # Użyj reload=True tylko podczas developmentu
    uvicorn.run("main:app", host="0.0.0.0", port=5002, reload=True)