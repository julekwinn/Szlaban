
import logging

# --- Konfiguracja Bazy Danych ---
DATABASE_FILE = "eszp.db"
TABLE_BARRIER_EVENTS = "barrier_events"
TABLE_USERS = "users"
TABLE_BARRIERS = "barriers"
TABLE_PERMISSIONS = "user_barrier_permissions"

# --- Konfiguracja Logowania ---
LOG_LEVEL = logging.INFO

# --- Konfiguracja Bezpieczeństwa ---
ADMIN_API_KEY = "ultra-tajny-admin-token-eszp-123" # Pamiętaj, aby zmienić to w środowisku produkcyjnym!
API_KEY_NAME = "X-Admin-API-Key"

# --- Inne Ustawienia ---
DEFAULT_EVENT_LIMIT = 50
MAX_EVENT_LIMIT = 1000
BARRIER_COMMAND_TIMEOUT = 15.0 # Sekundy