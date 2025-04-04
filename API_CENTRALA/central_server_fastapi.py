#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
import sqlite3 # Wciąż potrzebne dla type hint w zależnościach
from datetime import datetime
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status, Depends

# Importuj z nowych plików
import config
import models # Importuje wszystkie modele
import db     # Importuje wszystkie funkcje DB
import core   # Importuje funkcje core/security/dependencies

# --- Konfiguracja Logowania ---
logging.basicConfig(level=config.LOG_LEVEL, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
log = logging.getLogger(__name__)
# Zmniejszamy gadatliwość logów dostępowych uvicorna (opcjonalnie)
logging.getLogger('uvicorn.access').setLevel(logging.WARNING)

# --- Lifespan FastAPI ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Server startup...")
    db.init_db() # Uruchom inicjalizację bazy przy starcie
    yield
    log.info("Server shutdown...")

# --- Aplikacja FastAPI ---
app = FastAPI(
    title="Centrala ESZP v1.3 (Refactored)",
    description="API do zarządzania i kontroli szlabanów.",
    version="1.3.1", # Zwiększona wersja po refaktoryzacji
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
@app.get("/api/events", response_model=List[models.BarrierEventDBResponse], tags=["Admin"], dependencies=[Depends(core.verify_admin_token)])
async def get_all_events_endpoint(limit: int = config.DEFAULT_EVENT_LIMIT):
    """(Admin) Pobiera ostatnie zdarzenia ze WSZYSTKICH szlabanów."""
    events = db.get_events_from_db(barrier_ids=None, limit=limit, only_failures=False)
    if events is None: # get_events_from_db zwraca None w przypadku błędu DB
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve events from database.")
    # FastAPI automatycznie zwaliduje i przekonwertuje listę dict na listę BarrierEventDBResponse
    return events

@app.post("/api/users", response_model=models.UserResponse, status_code=status.HTTP_201_CREATED, tags=["Admin"], dependencies=[Depends(core.verify_admin_token)])
async def create_user_endpoint(user_data: models.UserCreate):
    """(Admin) Tworzy nowego użytkownika."""
    # Sprawdź, czy użytkownik już istnieje
    existing_user = db.get_user_by_username(user_data.username)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Username '{user_data.username}' already exists.")

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

@app.post("/api/barriers", response_model=models.BarrierResponse, status_code=status.HTTP_201_CREATED, tags=["Admin"], dependencies=[Depends(core.verify_admin_token)])
async def add_barrier_endpoint(barrier_data: models.BarrierCreate):
    """(Admin) Dodaje nowy szlaban (rejestruje jego ID i URL)."""
    # Prosta walidacja URL
    if not barrier_data.controller_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid controller_url format (must start with http:// or https://).")

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
        cursor_check.execute(f"SELECT 1 FROM {config.TABLE_BARRIERS} WHERE barrier_id=? OR controller_url=?", (barrier_data.barrier_id, barrier_data.controller_url))
        exists = cursor_check.fetchone()
        conn_check.close()
        if exists:
             raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Barrier ID or Controller URL already exists.")
        else: # Jeśli nie istnieje, a był błąd, to coś innego poszło nie tak
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error adding barrier.")

@app.post("/api/permissions", response_model=models.PermissionResponse, status_code=status.HTTP_201_CREATED, tags=["Admin"], dependencies=[Depends(core.verify_admin_token)])
async def grant_permission_endpoint(permission_data: models.PermissionCreate):
    """(Admin) Nadaje użytkownikowi uprawnienia do szlabanu."""
    # Znajdź użytkownika
    user = db.get_user_by_username(permission_data.username)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{permission_data.username}' not found.")

    # Nadaj uprawnienie
    permission_id, status_msg = db.grant_db_permission(user['id'], permission_data.barrier_id, permission_data.permission_level)

    if status_msg == "ok" and permission_id is not None:
        log.info(f"Admin granted '{permission_data.permission_level}' permission to user '{permission_data.username}' for barrier '{permission_data.barrier_id}'.")
        return models.PermissionResponse(
            id=permission_id,
            user_id=user['id'],
            username=permission_data.username, # Lub user['username']
            barrier_id=permission_data.barrier_id,
            permission_level=permission_data.permission_level
        )
    else:
        # Mapowanie kodu błędu z funkcji DB na status HTTP i komunikat
        error_details = {
            "permission_exists": (status.HTTP_409_CONFLICT, "Permission already exists for this user and barrier."),
            "barrier_not_found": (status.HTTP_404_NOT_FOUND, f"Barrier with ID '{permission_data.barrier_id}' not found."),
            "user_not_found": (status.HTTP_404_NOT_FOUND, f"User '{permission_data.username}' not found (consistency issue?)."), # Powinno być wykryte wcześniej
            "consistency_error": (status.HTTP_500_INTERNAL_SERVER_ERROR, "Database consistency error granting permission."),
            "db_error": (status.HTTP_500_INTERNAL_SERVER_ERROR, "Database error granting permission.")
        }
        status_code, detail_msg = error_details.get(status_msg, (status.HTTP_500_INTERNAL_SERVER_ERROR, "Unknown error granting permission."))
        log.warning(f"Failed to grant permission: {detail_msg} (User: {permission_data.username}, Barrier: {permission_data.barrier_id}, Status: {status_msg})")
        raise HTTPException(status_code=status_code, detail=detail_msg)

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


@app.post("/api/barriers/{barrier_id}/close", status_code=status.HTTP_202_ACCEPTED, tags=["User Actions"], summary="Zamyka wskazany szlaban")
async def close_barrier_endpoint(barrier_id: str, current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Wysyła komendę 'close' do wskazanego szlabanu. Działa jak /open."""
    await core.send_command_to_barrier(barrier_id, "close", current_user)

@app.post("/api/barriers/{barrier_id}/service/start", status_code=status.HTTP_202_ACCEPTED, tags=["User Actions"], summary="Włącza tryb serwisowy")
async def service_start_endpoint(barrier_id: str, current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Wysyła komendę 'service/start' (wymaga 'technician'). Działa jak /open."""
    await core.send_command_to_barrier(barrier_id, "service/start", current_user)

@app.post("/api/barriers/{barrier_id}/service/end", status_code=status.HTTP_202_ACCEPTED, tags=["User Actions"], summary="Wyłącza tryb serwisowy")
async def service_end_endpoint(barrier_id: str, current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Wysyła komendę 'service/end' (wymaga 'technician'). Działa jak /open."""
    await core.send_command_to_barrier(barrier_id, "service/end", current_user)

# == Grupa: User Info ==
@app.get("/api/my/barriers", response_model=List[models.MyBarrierResponse], tags=["User Info"])
async def get_my_barriers_endpoint(current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Zwraca listę szlabanów, do których zalogowany użytkownik ma dostęp."""
    barriers_details = db.get_user_authorized_barriers_details(current_user['id'])
    return barriers_details

@app.get("/api/my/events", response_model=List[models.BarrierEventDBResponse], tags=["User Info"])
async def get_my_events_endpoint(limit: int = config.DEFAULT_EVENT_LIMIT, current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Zwraca ostatnie zdarzenia z autoryzowanych szlabanów."""
    authorized_ids = db.get_user_authorized_barrier_ids(current_user['id'])
    if not authorized_ids:
        return [] # Użytkownik nie ma dostępu do żadnych szlabanów

    events = db.get_events_from_db(barrier_ids=authorized_ids, limit=limit)
    if events is None:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error reading events from database.")
    return events

@app.get("/api/barriers/{barrier_id}/events", response_model=List[models.BarrierEventDBResponse], tags=["User Info"])
async def get_specific_barrier_events_endpoint(barrier_id: str, limit: int = config.DEFAULT_EVENT_LIMIT, current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Zwraca ostatnie zdarzenia dla konkretnego, autoryzowanego szlabanu."""
    # Sprawdź uprawnienia do tego konkretnego szlabanu
    permission = db.get_db_permission_level(current_user['id'], barrier_id)
    if permission is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"No permission for barrier '{barrier_id}'.")

    # Pobierz zdarzenia tylko dla tego szlabanu
    events = db.get_events_from_db(barrier_ids=[barrier_id], limit=limit)
    if events is None:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error reading events from database.")
    return events

@app.get("/api/my/failures", response_model=List[models.BarrierEventDBResponse], tags=["User Info"])
async def get_my_failures_endpoint(limit: int = config.DEFAULT_EVENT_LIMIT, current_user: sqlite3.Row = Depends(core.get_current_user)):
    """(User) Zwraca ostatnie awarie (zdarzenia z success=false) z autoryzowanych szlabanów."""
    authorized_ids = db.get_user_authorized_barrier_ids(current_user['id'])
    if not authorized_ids:
        return []

    failure_events = db.get_events_from_db(barrier_ids=authorized_ids, limit=limit, only_failures=True)
    if failure_events is None:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error reading failure events from database.")
    return failure_events

if __name__ == "__main__":
    import uvicorn
    log.info("Starting Uvicorn server directly (for development only)...")
    # Użyj reload=True tylko podczas developmentu
    uvicorn.run("main:app", host="0.0.0.0", port=5002, reload=True)