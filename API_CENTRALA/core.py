# core.py
# -*- coding: utf-8 -*-

import logging
import sqlite3
import httpx
from typing import Optional
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends, Security
from fastapi.security import APIKeyHeader, HTTPBasic, HTTPBasicCredentials

# Importuj konfigurację i funkcje DB
import config
import db # Potrzebne do get_user_by_username, get_db_permission_level, get_barrier_controller_url

log = logging.getLogger(__name__)

# --- Konfiguracja Bezpieczeństwa (obiekty) ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
basic_security = HTTPBasic()
admin_api_key_header = APIKeyHeader(name=config.API_KEY_NAME, auto_error=False) # auto_error=False by móc zwrócić własny błąd

# --- Funkcje Pomocnicze Bezpieczeństwa ---
def verify_password(plain: str, hashed: str) -> bool:
    """Weryfikuje hasło jawne z hashem."""
    return pwd_context.verify(plain, hashed)

def get_password_hash(pwd: str) -> str:
    """Generuje hash hasła."""
    return pwd_context.hash(pwd)

# --- Zależności Autoryzacji FastAPI ---
async def verify_admin_token(api_key: str = Security(admin_api_key_header)):
    """Weryfikuje token admina przekazany w nagłówku."""
    if not api_key:
         raise HTTPException(
             status_code=status.HTTP_401_UNAUTHORIZED,
             detail="Missing Admin API Key (X-Admin-API-Key header)"
         )
    if api_key != config.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Admin API Key"
            )
    # Token jest poprawny, nie ma potrzeby nic zwracać

async def get_current_user(credentials: Optional[HTTPBasicCredentials] = Security(basic_security)) -> sqlite3.Row:
    """Weryfikuje dane logowania Basic Auth i zwraca obiekt użytkownika (Row)."""
    if credentials is None:
        log.warning("Basic Auth attempt failed: No credentials provided.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Basic"},
        )

    user = db.get_user_by_username(credentials.username)
    if user is None or not verify_password(credentials.password, user['hashed_password']):
        log.warning(f"Failed Basic Auth attempt for user '{credentials.username}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    log.info(f"User '{credentials.username}' authenticated via Basic Auth.")
    return user

# --- Pośrednik Komend do Szlabanów ---
async def send_command_to_barrier(barrier_id: str, action: str, current_user: sqlite3.Row):
    """
    Sprawdza uprawnienia, znajduje URL i wysyła komendę do kontrolera szlabanu.
    Zwraca odpowiedź kontrolera lub podnosi HTTPException w razie błędu.
    """
    user_id_db = current_user['id']
    username = current_user['username']

    # 1. Sprawdź poziom uprawnień
    permission_level = db.get_db_permission_level(user_id_db, barrier_id)
    if permission_level is None:
        log.warning(f"AuthZ Fail: User '{username}'(ID:{user_id_db}) has no permission for barrier '{barrier_id}'.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"No permission for barrier '{barrier_id}'.")

    # 2. Sprawdź, czy poziom wystarcza do akcji
    action_allowed = False
    if action in ["open", "close"] and permission_level in ["operator", "technician"]:
        action_allowed = True
    elif action in ["service/start", "service/end"] and permission_level == "technician":
        action_allowed = True

    if not action_allowed:
        log.warning(f"AuthZ Fail: User '{username}'(Lvl:{permission_level}) insufficient for action '{action}' on barrier '{barrier_id}'.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission level '{permission_level}' insufficient for action '{action}'.")

    # 3. Znajdź URL kontrolera
    controller_url = db.get_barrier_controller_url(barrier_id)
    if not controller_url:
        log.error(f"Config Error: Controller URL for barrier '{barrier_id}' not found in DB.")
        # Użyj 500, bo to błąd konfiguracji serwera centralnego
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Barrier controller URL not configured for ID '{barrier_id}'.")

    # 4. Wyślij komendę
    target_endpoint = f"/{action}" # Zakładamy, że URL kontrolera nie ma slasha na końcu
    full_url = controller_url.rstrip('/') + target_endpoint
    # Kluczowe: Przekazujemy ID użytkownika (z centrali) do kontrolera szlabanu
    # Kontroler może chcieć wiedzieć, kto inicjuje akcję
    headers = {'X-User-ID': str(user_id_db)}

    log.info(f"Proxy Cmd: User '{username}'(Lvl:{permission_level}) -> '{action}' @ '{barrier_id}' ({full_url})")

    async with httpx.AsyncClient(timeout=config.BARRIER_COMMAND_TIMEOUT) as client:
        try:
            response = await client.post(full_url, headers=headers)
            log.info(f"Proxy Response from {barrier_id} ({action}): Status={response.status_code}")

            # Próbujemy odczytać JSON, jeśli się nie uda, bierzemy tekst
            try:
                response_json = response.json()
            except Exception:
                response_json = {"raw_response": response.text}

            # Podnieś HTTPException ze statusem i ciałem odpowiedzi kontrolera
            # Niezależnie czy sukces (np. 200 OK) czy błąd (np. 400, 500) od kontrolera
            # Pozwala to klientowi API centrali zobaczyć, co odpowiedział szlaban
            # Status 202 Accepted z centrali był tylko potwierdzeniem przyjęcia żądania do proxy
            raise HTTPException(status_code=response.status_code, detail=response_json)

        except httpx.TimeoutException:
            log.error(f"Proxy Error: Timeout ({config.BARRIER_COMMAND_TIMEOUT}s) connecting to '{barrier_id}' ({full_url}).")
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=f"Timeout connecting to barrier '{barrier_id}'.")
        except httpx.RequestError as exc:
            log.error(f"Proxy Error: Connection error to '{barrier_id}' ({full_url}): {exc}")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Connection error to barrier '{barrier_id}': {exc}")
        except HTTPException as http_exc:
             # Przechwyć HTTPException podniesione powyżej (z odpowiedzi kontrolera)
             # i przekaż je dalej bez zmian
             raise http_exc
        except Exception as e:
             # Inne nieoczekiwane błędy podczas komunikacji
             log.exception(f"Proxy Error: Unexpected error sending command to '{barrier_id}': {e}")
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected proxy error: {e}")