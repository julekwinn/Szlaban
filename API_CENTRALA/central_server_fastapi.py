#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
import sqlite3
import httpx
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status, Depends, Security
from fastapi.security import APIKeyHeader, HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field, field_validator
from passlib.context import CryptContext

# --- Konfiguracja ---
DATABASE_FILE = "eszp.db"
TABLE_BARRIER_EVENTS = "barrier_events"
TABLE_USERS = "users"
TABLE_BARRIERS = "barriers"
TABLE_PERMISSIONS = "user_barrier_permissions"
LOG_LEVEL = logging.INFO

# --- Konfiguracja Bezpieczeństwa ---
ADMIN_API_KEY = "ultra-tajny-admin-token-eszp-123"
API_KEY_NAME = "X-Admin-API-Key"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
basic_security = HTTPBasic()
admin_api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

# --- Logowanie ---
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)
# Zmniejszamy gadatliwość logów dostępowych uvicorna
logging.getLogger('uvicorn.access').setLevel(logging.WARNING)

# --- Modele Pydantic ---

class BarrierEventBase(BaseModel):
    barrier_id: str
    event_type: str
    trigger_method: str
    timestamp: str # ISO 8601 string from controller
    user_id: Optional[str] = None
    success: bool
    details: Optional[str] = None
    failed_action: Optional[str] = None

class BarrierEventDBInput(BarrierEventBase): pass
class BarrierEventDBResponse(BarrierEventBase): id: int; received_at: str # ISO 8601 string from central server

class UserBase(BaseModel): username: str
class UserCreate(UserBase): password: str
class UserResponse(UserBase): id: int

class BarrierBase(BaseModel): barrier_id: str; controller_url: str
class BarrierCreate(BarrierBase): pass
class BarrierResponse(BarrierBase): id: int

class PermissionBase(BaseModel): username: str; barrier_id: str
class PermissionCreate(PermissionBase):
    permission_level: str
    @field_validator('permission_level')
    def v_perm_level(cls, v):
        allowed = {'operator', 'technician'}
        if v not in allowed: raise ValueError(f'must be one of {allowed}')
        return v
class PermissionResponse(PermissionBase): id: int; user_id: int; permission_level: str

class MyBarrierResponse(BaseModel): barrier_id: str; controller_url: str; permission_level: str

# --- Funkcje Pomocnicze Bezpieczeństwa ---

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def get_password_hash(pwd: str) -> str:
    return pwd_context.hash(pwd)

# --- Funkcje Bazy Danych ---

def get_db():
    """Zwraca połączenie do bazy SQLite z row_factory."""
    conn = sqlite3.connect(DATABASE_FILE, timeout=10) # Dodano timeout
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inicjalizuje schemat bazy danych."""
    log.info(f"DB Init: Checking schema in {DATABASE_FILE}...")
    try:
        conn = get_db()
        cursor = conn.cursor()
        # Włącz obsługę kluczy obcych (ważne dla ON DELETE CASCADE)
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Tabele (kolejność ma znaczenie ze względu na klucze obce)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_USERS} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                hashed_password TEXT NOT NULL
            )""")
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_BARRIERS} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barrier_id TEXT NOT NULL UNIQUE,
                controller_url TEXT NOT NULL UNIQUE
            )""")
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_PERMISSIONS} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                barrier_id TEXT NOT NULL,
                permission_level TEXT NOT NULL CHECK(permission_level IN ('operator', 'technician')),
                FOREIGN KEY (user_id) REFERENCES {TABLE_USERS} (id) ON DELETE CASCADE,
                FOREIGN KEY (barrier_id) REFERENCES {TABLE_BARRIERS} (barrier_id) ON DELETE CASCADE,
                UNIQUE(user_id, barrier_id)
            )""")
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_BARRIER_EVENTS} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barrier_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                trigger_method TEXT NOT NULL,
                event_timestamp TEXT NOT NULL,
                user_id TEXT,
                success INTEGER NOT NULL,
                details TEXT,
                failed_action TEXT,
                received_at TEXT NOT NULL
            )""")

        conn.commit()
        log.info("DB Init: Schema verified/created successfully.")
        conn.close()
    except sqlite3.Error as e:
        log.exception(f"DB Init Error: Failed to initialize database schema: {e}")
        raise # Zatrzymujemy aplikację, jeśli baza nie działa

# --- Funkcje Dostępu do Danych (CRUD i inne) ---

def add_event_to_db(event: BarrierEventDBInput, received_at: str) -> bool:
    sql = f"INSERT INTO {TABLE_BARRIER_EVENTS} (barrier_id, event_type, trigger_method, event_timestamp, user_id, success, details, failed_action, received_at) VALUES (?,?,?,?,?,?,?,?,?)"
    params = (event.barrier_id, event.event_type, event.trigger_method, event.timestamp, event.user_id, 1 if event.success else 0, event.details, event.failed_action, received_at)
    try:
        conn = get_db(); conn.execute(sql, params); conn.commit(); conn.close(); return True
    except sqlite3.Error as e: log.error(f"DB Event Save Error: {e}"); return False

def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    try: conn = get_db(); cursor = conn.cursor(); cursor.execute(f"SELECT * FROM {TABLE_USERS} WHERE username = ?", (username,)); user = cursor.fetchone(); conn.close(); return user
    except sqlite3.Error as e: log.error(f"DB Get User Error: {e}"); return None

def create_db_user(username: str, hashed_password: str) -> Optional[int]:
    sql = f"INSERT INTO {TABLE_USERS} (username, hashed_password) VALUES (?, ?)"
    try: conn = get_db(); cursor = conn.cursor(); cursor.execute(sql, (username, hashed_password)); user_id = cursor.lastrowid; conn.commit(); conn.close(); return user_id
    except sqlite3.IntegrityError: return None # Username exists
    except sqlite3.Error as e: log.error(f"DB User Create Error: {e}"); return None

def create_db_barrier(barrier_id: str, controller_url: str) -> Optional[int]:
    sql = f"INSERT INTO {TABLE_BARRIERS} (barrier_id, controller_url) VALUES (?, ?)"
    try: conn = get_db(); cursor = conn.cursor(); cursor.execute(sql, (barrier_id, controller_url)); db_id = cursor.lastrowid; conn.commit(); conn.close(); return db_id
    except sqlite3.IntegrityError: return None # Barrier ID or URL exists
    except sqlite3.Error as e: log.error(f"DB Barrier Create Error: {e}"); return None

def grant_db_permission(user_id: int, barrier_id: str, permission_level: str) -> Tuple[Optional[int], str]:
    conn = get_db(); cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON;") # Upewnij się, że FK są włączone dla tej sesji
        cursor.execute(f"SELECT 1 FROM {TABLE_BARRIERS} WHERE barrier_id = ?", (barrier_id,))
        if not cursor.fetchone(): return None, "barrier_not_found"
        cursor.execute(f"SELECT 1 FROM {TABLE_USERS} WHERE id = ?", (user_id,))
        if not cursor.fetchone(): return None, "user_not_found"
        sql = f"INSERT INTO {TABLE_PERMISSIONS} (user_id, barrier_id, permission_level) VALUES (?, ?, ?)"
        cursor.execute(sql, (user_id, barrier_id, permission_level))
        permission_id = cursor.lastrowid; conn.commit(); return permission_id, "ok"
    except sqlite3.IntegrityError: # Obsługa UNIQUE constraint lub FOREIGN KEY constraint
        conn.rollback()
        cursor.execute(f"SELECT 1 FROM {TABLE_PERMISSIONS} WHERE user_id = ? AND barrier_id = ?", (user_id, barrier_id))
        if cursor.fetchone(): return None, "permission_exists"
        else: return None, "consistency_error" # Prawdopodobnie FK violation (choć sprawdziliśmy)
    except sqlite3.Error as e: conn.rollback(); log.error(f"DB Perm Grant Error: {e}"); return None, "db_error"
    finally: conn.close()

def get_db_permission_level(user_id: int, barrier_id: str) -> Optional[str]:
    sql = f"SELECT permission_level FROM {TABLE_PERMISSIONS} WHERE user_id = ? AND barrier_id = ?"
    try: conn = get_db(); cursor = conn.cursor(); cursor.execute(sql, (user_id, barrier_id)); perm = cursor.fetchone(); conn.close(); return perm['permission_level'] if perm else None
    except sqlite3.Error as e: log.error(f"DB Get Perm Level Error: {e}"); return None

def get_barrier_controller_url(barrier_id: str) -> Optional[str]:
    sql = f"SELECT controller_url FROM {TABLE_BARRIERS} WHERE barrier_id = ?"
    try: conn = get_db(); cursor = conn.cursor(); cursor.execute(sql, (barrier_id,)); result = cursor.fetchone(); conn.close(); return result['controller_url'] if result else None
    except sqlite3.Error as e: log.error(f"DB Get Barrier URL Error: {e}"); return None

def get_user_authorized_barrier_ids(user_id: int) -> List[str]:
    sql = f"SELECT barrier_id FROM {TABLE_PERMISSIONS} WHERE user_id = ?"
    try: conn = get_db(); cursor = conn.cursor(); cursor.execute(sql, (user_id,)); rows = cursor.fetchall(); conn.close(); return [row['barrier_id'] for row in rows]
    except sqlite3.Error as e: log.error(f"DB Get Auth Barriers Error: {e}"); return []

def get_user_authorized_barriers_details(user_id: int) -> List[Dict]:
    sql = f"SELECT b.barrier_id, b.controller_url, p.permission_level FROM {TABLE_PERMISSIONS} p JOIN {TABLE_BARRIERS} b ON p.barrier_id = b.barrier_id WHERE p.user_id = ?"
    try: conn = get_db(); cursor = conn.cursor(); cursor.execute(sql, (user_id,)); rows = cursor.fetchall(); conn.close(); return [dict(row) for row in rows]
    except sqlite3.Error as e: log.error(f"DB Get Auth Barrier Details Error: {e}"); return []

def _map_event_row_to_dict(row: sqlite3.Row) -> Dict:
    """Pomocnik do konwersji wiersza zdarzenia na słownik."""
    event_dict = dict(row)
    event_dict['timestamp'] = event_dict.pop('event_timestamp') # Zmiana nazwy klucza
    event_dict['success'] = bool(event_dict['success']) # Konwersja int na bool
    return event_dict

def get_events_from_db(barrier_ids: Optional[List[str]] = None, limit: int = 50, only_failures: bool = False) -> List[Dict]:
    """Pobiera zdarzenia z bazy, opcjonalnie filtrując po ID szlabanów i awariach."""
    if barrier_ids is not None and not barrier_ids: return [] # Pusta lista ID = brak wyników
    if not 1 <= limit <= 1000: limit = 50 # Ograniczenie limitu

    params = []
    sql_where_parts = []

    if barrier_ids is not None:
        placeholders = ','.join('?' * len(barrier_ids))
        sql_where_parts.append(f"barrier_id IN ({placeholders})")
        params.extend(barrier_ids)

    if only_failures:
        sql_where_parts.append("success = 0")

    sql_where = f"WHERE {' AND '.join(sql_where_parts)}" if sql_where_parts else ""
    sql = f"SELECT * FROM {TABLE_BARRIER_EVENTS} {sql_where} ORDER BY id DESC LIMIT ?"
    params.append(limit)

    try:
        conn = get_db(); cursor = conn.cursor(); cursor.execute(sql, params); rows = cursor.fetchall(); conn.close()
        return [_map_event_row_to_dict(row) for row in rows]
    except sqlite3.Error as e:
        log.error(f"DB Read Events Error: {e}")
        return []

# --- Zależności Autoryzacji FastAPI ---

async def verify_admin_token(api_key: str = Security(admin_api_key_header)):
    """Weryfikuje token admina przekazany w nagłówku."""
    if api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing Admin API Key")
    # Nie ma potrzeby zwracać True, sama weryfikacja wystarczy

async def get_current_user(credentials: HTTPBasicCredentials = Security(basic_security)) -> sqlite3.Row:
    """Weryfikuje dane logowania Basic Auth i zwraca obiekt użytkownika (Row)."""
    user = get_user_by_username(credentials.username)
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
    """Helper: Sprawdza uprawnienia, znajduje URL i wysyła komendę do kontrolera szlabanu."""
    user_id_db = current_user['id']
    username = current_user['username']

    # 1. Sprawdź poziom uprawnień
    permission_level = get_db_permission_level(user_id_db, barrier_id)
    if permission_level is None:
        log.warning(f"AuthZ Fail: User '{username}'(ID:{user_id_db}) no permission for barrier '{barrier_id}'.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"No permission for barrier '{barrier_id}'.")

    # 2. Sprawdź, czy poziom wystarcza do akcji
    action_allowed = False
    if action in ["open", "close"] and permission_level in ["operator", "technician"]: action_allowed = True
    elif action in ["service/start", "service/end"] and permission_level == "technician": action_allowed = True

    if not action_allowed:
        log.warning(f"AuthZ Fail: User '{username}'(Lvl:{permission_level}) insufficient for action '{action}' on barrier '{barrier_id}'.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission level '{permission_level}' insufficient for action '{action}'.")

    # 3. Znajdź URL kontrolera
    controller_url = get_barrier_controller_url(barrier_id)
    if not controller_url:
        log.error(f"Config Error: Controller URL for barrier '{barrier_id}' not found in DB.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Barrier controller URL not configured for ID '{barrier_id}'.")

    # 4. Wyślij komendę
    target_endpoint = f"/{action}"
    full_url = controller_url.rstrip('/') + target_endpoint
    # Kluczowe: Przekazujemy ID użytkownika (z centrali) do kontrolera szlabanu
    headers = {'X-User-ID': str(user_id_db)}

    log.info(f"Proxy Cmd: User '{username}'(Lvl:{permission_level}) -> '{action}' @ '{barrier_id}' ({full_url})")

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(full_url, headers=headers)
            log.info(f"Proxy Response from {barrier_id}: Status={response.status_code}")

            # Spróbuj sparsować odpowiedź jako JSON, jeśli nie, zwróć tekst
            try: response_json = response.json()
            except Exception: response_json = {"raw_response": response.text}

            # Podnieś HTTPException ze statusem i ciałem odpowiedzi kontrolera
            # Pozwala to klientowi centrali zobaczyć, co się stało na szlabanie
            raise HTTPException(status_code=response.status_code, detail=response_json)

        except httpx.TimeoutException:
            log.error(f"Proxy Error: Timeout connecting to '{barrier_id}' ({full_url}).")
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=f"Timeout connecting to barrier '{barrier_id}'.")
        except httpx.RequestError as exc:
            log.error(f"Proxy Error: Connection error to '{barrier_id}' ({full_url}): {exc}")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Connection error to barrier '{barrier_id}': {exc}")
        except HTTPException as http_exc:
             # Przechwyć HTTPException podniesione powyżej, aby przekazać odpowiedź kontrolera
             raise http_exc
        except Exception as e:
             log.exception(f"Proxy Error: Unexpected error sending command to '{barrier_id}': {e}")
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected proxy error: {e}")


# --- Lifespan FastAPI ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Server startup...")
    init_db() # Uruchom inicjalizację bazy przy starcie
    yield
    log.info("Server shutdown...")

# --- Aplikacja FastAPI ---
app = FastAPI(
    title="Centrala ESZP v1.3",
    description="API do zarządzania i kontroli szlabanów.",
    version="1.3.0",
    lifespan=lifespan
)

# --- Endpointy API ---

# == Grupa: Events ==
@app.post("/barrier/event", status_code=status.HTTP_200_OK, tags=["Events"])
async def receive_barrier_event_endpoint(event_data: BarrierEventDBInput):
    """Odbiera zdarzenie od kontrolera szlabanu i zapisuje do bazy."""
    if add_event_to_db(event_data, datetime.now().isoformat()):
        return {"status": "received_ok"}
    else:
        # Logowanie błędu odbywa się w add_event_to_db
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save event data.")

# == Grupa: Admin ==
@app.get("/api/events", response_model=List[BarrierEventDBResponse], tags=["Admin"], dependencies=[Depends(verify_admin_token)])
async def get_all_events_endpoint(limit: int = 100):
    """(Admin) Pobiera ostatnie zdarzenia ze WSZYSTKICH szlabanów."""
    events = get_events_from_db(barrier_ids=None, limit=limit, only_failures=False) # None oznacza wszystkie
    if events is None: # Obsługa potencjalnego błędu z DB
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve events from database.")
    return events

@app.post("/api/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["Admin"], dependencies=[Depends(verify_admin_token)])
async def create_user_endpoint(user_data: UserCreate):
    """(Admin) Tworzy nowego użytkownika."""
    if get_user_by_username(user_data.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists.")
    hashed_password = get_password_hash(user_data.password)
    user_id = create_db_user(user_data.username, hashed_password)
    if user_id:
        log.info(f"Admin created user '{user_data.username}' (ID: {user_id}).")
        return {"id": user_id, "username": user_data.username}
    else:
        # Logowanie błędu w create_db_user
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error creating user.")

@app.post("/api/barriers", response_model=BarrierResponse, status_code=status.HTTP_201_CREATED, tags=["Admin"], dependencies=[Depends(verify_admin_token)])
async def add_barrier_endpoint(barrier_data: BarrierCreate):
    """(Admin) Dodaje nowy szlaban (rejestruje jego ID i URL)."""
    if not barrier_data.controller_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid controller_url format (must start with http:// or https://).")
    db_id = create_db_barrier(barrier_data.barrier_id, barrier_data.controller_url)
    if db_id:
        log.info(f"Admin added barrier '{barrier_data.barrier_id}'.")
        # Użyj model_dump() do konwersji Pydantic na dict
        return {"id": db_id, **barrier_data.model_dump()}
    else:
        # Sprawdź czy istnieje, czy inny błąd
        conn=get_db(); cursor=conn.cursor(); cursor.execute(f"SELECT 1 FROM {TABLE_BARRIERS} WHERE barrier_id=? OR controller_url=?",(barrier_data.barrier_id,barrier_data.controller_url)); e=cursor.fetchone(); conn.close()
        if e: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Barrier ID or Controller URL already exists.")
        else: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error adding barrier.")

@app.post("/api/permissions", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED, tags=["Admin"], dependencies=[Depends(verify_admin_token)])
async def grant_permission_endpoint(permission_data: PermissionCreate):
    """(Admin) Nadaje użytkownikowi uprawnienia do szlabanu."""
    user = get_user_by_username(permission_data.username)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{permission_data.username}' not found.")

    permission_id, status_msg = grant_db_permission(user['id'], permission_data.barrier_id, permission_data.permission_level)

    if status_msg == "ok":
        log.info(f"Admin granted '{permission_data.permission_level}' permission to user '{permission_data.username}' for barrier '{permission_data.barrier_id}'.")
        # Użyj model_dump() do konwersji Pydantic na dict
        return {"id": permission_id, "user_id": user['id'], **permission_data.model_dump()}
    else:
        # Mapowanie kodu błędu z funkcji DB na status HTTP
        status_code = {
            "permission_exists": 409, "barrier_not_found": 404,
            "user_not_found": 404, "consistency_error": 500, "db_error": 500
        }.get(status_msg, 500)
        detail_msg = status_msg.replace("_", " ").title()
        log.warning(f"Failed to grant permission: {detail_msg} (User: {permission_data.username}, Barrier: {permission_data.barrier_id})")
        raise HTTPException(status_code=status_code, detail=detail_msg)

# == Grupa: User Actions ==
@app.post("/api/barriers/{barrier_id}/open", status_code=status.HTTP_202_ACCEPTED, tags=["User Actions"])
async def open_barrier_endpoint(barrier_id: str, current_user: sqlite3.Row = Depends(get_current_user)):
    """(User) Otwiera wskazany szlaban."""
    return await send_command_to_barrier(barrier_id, "open", current_user)

@app.post("/api/barriers/{barrier_id}/close", status_code=status.HTTP_202_ACCEPTED, tags=["User Actions"])
async def close_barrier_endpoint(barrier_id: str, current_user: sqlite3.Row = Depends(get_current_user)):
    """(User) Zamyka wskazany szlaban."""
    return await send_command_to_barrier(barrier_id, "close", current_user)

@app.post("/api/barriers/{barrier_id}/service/start", status_code=status.HTTP_202_ACCEPTED, tags=["User Actions"])
async def service_start_endpoint(barrier_id: str, current_user: sqlite3.Row = Depends(get_current_user)):
    """(User) Włącza tryb serwisowy (wymaga 'technician')."""
    return await send_command_to_barrier(barrier_id, "service/start", current_user)

@app.post("/api/barriers/{barrier_id}/service/end", status_code=status.HTTP_202_ACCEPTED, tags=["User Actions"])
async def service_end_endpoint(barrier_id: str, current_user: sqlite3.Row = Depends(get_current_user)):
    """(User) Wyłącza tryb serwisowy (wymaga 'technician')."""
    return await send_command_to_barrier(barrier_id, "service/end", current_user)

# == Grupa: User Info ==
@app.get("/api/my/barriers", response_model=List[MyBarrierResponse], tags=["User Info"])
async def get_my_barriers_endpoint(current_user: sqlite3.Row = Depends(get_current_user)):
    """(User) Zwraca listę szlabanów, do których użytkownik ma dostęp."""
    barriers = get_user_authorized_barriers_details(current_user['id'])
    if barriers is None: # Obsługa potencjalnego błędu z DB
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error reading permissions.")
    return barriers

@app.get("/api/my/events", response_model=List[BarrierEventDBResponse], tags=["User Info"])
async def get_my_events_endpoint(limit: int = 50, current_user: sqlite3.Row = Depends(get_current_user)):
    """(User) Zwraca ostatnie zdarzenia z autoryzowanych szlabanów."""
    authorized_ids = get_user_authorized_barrier_ids(current_user['id'])
    events = get_events_from_db(barrier_ids=authorized_ids, limit=limit)
    if events is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error reading events.")
    return events

@app.get("/api/barriers/{barrier_id}/events", response_model=List[BarrierEventDBResponse], tags=["User Info"])
async def get_specific_barrier_events_endpoint(barrier_id: str, limit: int = 50, current_user: sqlite3.Row = Depends(get_current_user)):
    """(User) Zwraca ostatnie zdarzenia dla konkretnego autoryzowanego szlabanu."""
    permission = get_db_permission_level(current_user['id'], barrier_id)
    if permission is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"No permission for barrier '{barrier_id}'.")
    events = get_events_from_db(barrier_ids=[barrier_id], limit=limit)
    if events is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error reading events.")
    return events

@app.get("/api/my/failures", response_model=List[BarrierEventDBResponse], tags=["User Info"])
async def get_my_failures_endpoint(limit: int = 50, current_user: sqlite3.Row = Depends(get_current_user)):
    """(User) Zwraca ostatnie awarie z autoryzowanych szlabanów."""
    authorized_ids = get_user_authorized_barrier_ids(current_user['id'])
    failure_events = get_events_from_db(barrier_ids=authorized_ids, limit=limit, only_failures=True)
    if failure_events is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error reading failure events.")
    return failure_events

# --- Uruchomienie ---
# uvicorn central_server_fastapi:app --reload --host 0.0.0.0 --port 5001