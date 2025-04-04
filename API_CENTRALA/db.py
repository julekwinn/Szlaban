# db.py
# -*- coding: utf-8 -*-

import sqlite3
import logging
from typing import Optional, List, Dict, Tuple
from datetime import datetime

# Importuj konfigurację i modele
import config
import models # Zakładamy, że modele są w models.py

log = logging.getLogger(__name__)

# --- Funkcje Połączenia i Inicjalizacji ---

def get_db() -> sqlite3.Connection:
    """Zwraca połączenie do bazy SQLite z row_factory."""
    try:
        conn = sqlite3.connect(config.DATABASE_FILE, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;") # Włącz FK dla każdej sesji
        return conn
    except sqlite3.Error as e:
        log.exception(f"DB Connection Error: Failed to connect to {config.DATABASE_FILE}: {e}")
        raise # Rzuć wyjątek dalej, aby zatrzymać aplikację w razie problemów z DB

def init_db():
    """Inicjalizuje schemat bazy danych, jeśli tabele nie istnieją."""
    log.info(f"DB Init: Checking schema in {config.DATABASE_FILE}...")
    try:
        with get_db() as conn: # Używamy context manager
            cursor = conn.cursor()
            # Włącz obsługę kluczy obcych (już w get_db, ale dla pewności)
            cursor.execute("PRAGMA foreign_keys = ON;")

            # Tabele (kolejność ma znaczenie ze względu na klucze obce)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {config.TABLE_USERS} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    hashed_password TEXT NOT NULL
                )""")
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {config.TABLE_BARRIERS} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    barrier_id TEXT NOT NULL UNIQUE,
                    controller_url TEXT NOT NULL UNIQUE
                )""")
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {config.TABLE_PERMISSIONS} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    barrier_id TEXT NOT NULL,
                    permission_level TEXT NOT NULL CHECK(permission_level IN ('operator', 'technician')),
                    FOREIGN KEY (user_id) REFERENCES {config.TABLE_USERS} (id) ON DELETE CASCADE,
                    FOREIGN KEY (barrier_id) REFERENCES {config.TABLE_BARRIERS} (barrier_id) ON DELETE CASCADE,
                    UNIQUE(user_id, barrier_id)
                )""")
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {config.TABLE_BARRIER_EVENTS} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    barrier_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    trigger_method TEXT NOT NULL,
                    event_timestamp TEXT NOT NULL, -- Oryginalny czas zdarzenia
                    user_id TEXT,
                    success INTEGER NOT NULL, -- 0 or 1
                    details TEXT,
                    failed_action TEXT,
                    received_at TEXT NOT NULL -- Czas odebrania przez centralę
                )""")

            conn.commit()
            log.info("DB Init: Schema verified/created successfully.")
    except sqlite3.Error as e:
        log.exception(f"DB Init Error: Failed to initialize database schema: {e}")
        raise # Zatrzymujemy aplikację, jeśli baza nie działa poprawnie przy starcie

# --- Funkcje Dostępu do Danych (CRUD i inne) ---

def add_event_to_db(event: models.BarrierEventDBInput, received_at: str) -> bool:
    """Zapisuje zdarzenie szlabanu do bazy danych."""
    sql = f"""INSERT INTO {config.TABLE_BARRIER_EVENTS}
              (barrier_id, event_type, trigger_method, event_timestamp, user_id, success, details, failed_action, received_at)
              VALUES (?,?,?,?,?,?,?,?,?)"""
    params = (
        event.barrier_id, event.event_type, event.trigger_method, event.timestamp,
        event.user_id, 1 if event.success else 0, event.details, event.failed_action, received_at
    )
    try:
        with get_db() as conn:
            conn.execute(sql, params)
            conn.commit()
        log.debug(f"Event from barrier '{event.barrier_id}' saved successfully.")
        return True
    except sqlite3.Error as e:
        log.error(f"DB Event Save Error: Failed to save event for barrier '{event.barrier_id}'. Error: {e}")
        return False

def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    """Pobiera dane użytkownika na podstawie nazwy."""
    sql = f"SELECT * FROM {config.TABLE_USERS} WHERE username = ?"
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (username,))
            user = cursor.fetchone()
        return user
    except sqlite3.Error as e:
        log.error(f"DB Get User Error: Failed fetching user '{username}'. Error: {e}")
        return None

def create_db_user(username: str, hashed_password: str) -> Optional[int]:
    """Tworzy nowego użytkownika w bazie danych."""
    sql = f"INSERT INTO {config.TABLE_USERS} (username, hashed_password) VALUES (?, ?)"
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (username, hashed_password))
            user_id = cursor.lastrowid
            conn.commit()
        log.info(f"User '{username}' created with ID: {user_id}.")
        return user_id
    except sqlite3.IntegrityError: # Username exists (UNIQUE constraint)
        log.warning(f"DB User Create Error: Username '{username}' already exists.")
        return None
    except sqlite3.Error as e:
        log.error(f"DB User Create Error: Failed creating user '{username}'. Error: {e}")
        return None

def create_db_barrier(barrier_id: str, controller_url: str) -> Optional[int]:
    """Dodaje nowy szlaban do bazy danych."""
    sql = f"INSERT INTO {config.TABLE_BARRIERS} (barrier_id, controller_url) VALUES (?, ?)"
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (barrier_id, controller_url))
            db_id = cursor.lastrowid
            conn.commit()
        log.info(f"Barrier '{barrier_id}' added with ID: {db_id}.")
        return db_id
    except sqlite3.IntegrityError: # Barrier ID or URL exists (UNIQUE constraint)
        log.warning(f"DB Barrier Create Error: Barrier ID '{barrier_id}' or URL '{controller_url}' already exists.")
        return None
    except sqlite3.Error as e:
        log.error(f"DB Barrier Create Error: Failed adding barrier '{barrier_id}'. Error: {e}")
        return None

def grant_db_permission(user_id: int, barrier_id: str, permission_level: str) -> Tuple[Optional[int], str]:
    """Nadaje użytkownikowi uprawnienia do szlabanu."""
    # Sprawdzenie czy user i barrier istnieją może być pomocne, ale FK constraint powinien to załatwić
    sql = f"INSERT INTO {config.TABLE_PERMISSIONS} (user_id, barrier_id, permission_level) VALUES (?, ?, ?)"
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            # Sprawdzenie istnienia użytkownika i szlabanu (opcjonalne, FK to obsłuży)
            cursor.execute(f"SELECT 1 FROM {config.TABLE_USERS} WHERE id = ?", (user_id,))
            if not cursor.fetchone(): return None, "user_not_found"
            cursor.execute(f"SELECT 1 FROM {config.TABLE_BARRIERS} WHERE barrier_id = ?", (barrier_id,))
            if not cursor.fetchone(): return None, "barrier_not_found"

            # Dodanie uprawnienia
            cursor.execute(sql, (user_id, barrier_id, permission_level))
            permission_id = cursor.lastrowid
            conn.commit()
        log.info(f"Permission '{permission_level}' granted for user ID {user_id} to barrier '{barrier_id}'. Permission ID: {permission_id}.")
        return permission_id, "ok"
    except sqlite3.IntegrityError as e:
        # Sprawdźmy, czy to błąd unikalności (już istnieje) czy błąd klucza obcego
        conn_check = get_db()
        cursor_check = conn_check.cursor()
        cursor_check.execute(f"SELECT 1 FROM {config.TABLE_PERMISSIONS} WHERE user_id = ? AND barrier_id = ?", (user_id, barrier_id))
        exists = cursor_check.fetchone()
        conn_check.close()
        if exists:
            log.warning(f"DB Perm Grant Error: Permission already exists for user {user_id} on barrier '{barrier_id}'.")
            return None, "permission_exists"
        else:
            # Jeśli nie istnieje, a jest IntegrityError, to prawdopodobnie FK (choć sprawdzaliśmy) lub inny
            log.error(f"DB Perm Grant Integrity Error (potential FK issue or other): User {user_id}, Barrier '{barrier_id}'. Error: {e}")
            return None, "consistency_error" # Może być błąd FK mimo sprawdzenia - race condition?
    except sqlite3.Error as e:
        log.error(f"DB Perm Grant Error: User {user_id}, Barrier '{barrier_id}'. Error: {e}")
        return None, "db_error"

def get_db_permission_level(user_id: int, barrier_id: str) -> Optional[str]:
    """Pobiera poziom uprawnień użytkownika do danego szlabanu."""
    sql = f"SELECT permission_level FROM {config.TABLE_PERMISSIONS} WHERE user_id = ? AND barrier_id = ?"
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (user_id, barrier_id))
            perm = cursor.fetchone()
        return perm['permission_level'] if perm else None
    except sqlite3.Error as e:
        log.error(f"DB Get Perm Level Error: User {user_id}, Barrier '{barrier_id}'. Error: {e}")
        return None

def get_barrier_controller_url(barrier_id: str) -> Optional[str]:
    """Pobiera URL kontrolera dla danego szlabanu."""
    sql = f"SELECT controller_url FROM {config.TABLE_BARRIERS} WHERE barrier_id = ?"
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (barrier_id,))
            result = cursor.fetchone()
        return result['controller_url'] if result else None
    except sqlite3.Error as e:
        log.error(f"DB Get Barrier URL Error: Barrier '{barrier_id}'. Error: {e}")
        return None

def get_user_authorized_barrier_ids(user_id: int) -> List[str]:
    """Pobiera listę ID szlabanów, do których użytkownik ma dostęp."""
    sql = f"SELECT barrier_id FROM {config.TABLE_PERMISSIONS} WHERE user_id = ?"
    ids = []
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (user_id,))
            rows = cursor.fetchall()
        ids = [row['barrier_id'] for row in rows]
        return ids
    except sqlite3.Error as e:
        log.error(f"DB Get Auth Barriers Error: User {user_id}. Error: {e}")
        return [] # Zwróć pustą listę w razie błędu

def get_user_authorized_barriers_details(user_id: int) -> List[Dict]:
    """Pobiera szczegóły szlabanów, do których użytkownik ma dostęp."""
    sql = f"""SELECT b.barrier_id, b.controller_url, p.permission_level
              FROM {config.TABLE_PERMISSIONS} p
              JOIN {config.TABLE_BARRIERS} b ON p.barrier_id = b.barrier_id
              WHERE p.user_id = ?"""
    details = []
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (user_id,))
            rows = cursor.fetchall()
        details = [dict(row) for row in rows]
        return details
    except sqlite3.Error as e:
        log.error(f"DB Get Auth Barrier Details Error: User {user_id}. Error: {e}")
        return [] # Zwróć pustą listę w razie błędu

def _map_event_row_to_dict(row: sqlite3.Row) -> Dict:
    """Pomocnik do konwersji wiersza zdarzenia z bazy na słownik zgodny z modelem."""
    if not row:
        return {}
    event_dict = dict(row)
    # Poprawka nazwy pola timestamp i konwersja success na bool
    if 'event_timestamp' in event_dict:
         event_dict['timestamp'] = event_dict.pop('event_timestamp')
    if 'success' in event_dict:
         event_dict['success'] = bool(event_dict['success']) # Konwersja 0/1 na False/True
    return event_dict

def get_events_from_db(barrier_ids: Optional[List[str]] = None, limit: int = config.DEFAULT_EVENT_LIMIT, only_failures: bool = False) -> Optional[List[Dict]]:
    """Pobiera zdarzenia z bazy, opcjonalnie filtrując po ID szlabanów i awariach."""
    if barrier_ids is not None and not barrier_ids:
        return [] # Pusta lista ID = brak wyników, nie błąd

    # Walidacja i ograniczenie limitu
    if not (1 <= limit <= config.MAX_EVENT_LIMIT):
        limit = config.DEFAULT_EVENT_LIMIT
        log.warning(f"Invalid limit provided. Using default limit: {limit}")


    params = []
    sql_where_parts = []

    if barrier_ids is not None:
        # Zabezpieczenie przed SQL Injection (chociaż tu parametryzujemy)
        safe_barrier_ids = [str(bid) for bid in barrier_ids]
        placeholders = ','.join('?' * len(safe_barrier_ids))
        sql_where_parts.append(f"barrier_id IN ({placeholders})")
        params.extend(safe_barrier_ids)

    if only_failures:
        sql_where_parts.append("success = 0") # 0 oznacza false w bazie

    sql_where = f"WHERE {' AND '.join(sql_where_parts)}" if sql_where_parts else ""
    sql = f"SELECT * FROM {config.TABLE_BARRIER_EVENTS} {sql_where} ORDER BY id DESC LIMIT ?"
    params.append(limit)

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        # Użyj _map_event_row_to_dict do konwersji każdego wiersza
        return [_map_event_row_to_dict(row) for row in rows]
    except sqlite3.Error as e:
        log.error(f"DB Read Events Error: Failed fetching events. Filter: barrier_ids={barrier_ids}, only_failures={only_failures}. Error: {e}")
        return None # Zwróć None w przypadku błędu odczytu z bazy