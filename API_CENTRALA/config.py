import logging


# --- Konfiguracja Bazy Danych ---
DATABASE_FILE = "eszp.db"
TABLE_BARRIER_EVENTS = "barrier_events"
TABLE_USERS = "users"
TABLE_BARRIERS = "barriers"
TABLE_PERMISSIONS = "user_barrier_permissions"
TABLE_REMOTES = "remotes"  # Nowa tabela dla pilotów

# --- Konfiguracja Logowania ---
LOG_LEVEL = logging.INFO

# --- Konfiguracja Bezpieczeństwa ---
ADMIN_API_KEY = "ultra-tajny-admin-token-eszp-123" # Pamiętaj, aby zmienić to w środowisku produkcyjnym!
API_KEY_NAME = "X-Admin-API-Key"

# --- Konfiguracja Pilotów ---
PILOT_ID_LENGTH = 8       # Długość identyfikatora pilota w bajtach
CRYPTO_AES_KEY_LENGTH = 16  # Długość klucza AES w bajtach (128 bitów)
CRYPTO_HMAC_KEY_LENGTH = 32 # Długość klucza HMAC w bajtach (256 bitów)
CRYPTO_IV_LENGTH = 16       # Długość wektora inicjalizacyjnego w bajtach

# --- Konfiguracja Generatora ---
CONFIG_TEMPLATE = """/* Automatycznie wygenerowane przez ESZP Centralę v1.3 */
#include "config.h"

/* Identyfikator pilota - {name} */
const uint8_t PILOT_ID[PILOT_ID_LENGTH] = {{
{pilot_id_bytes}
}};

/* Klucz AES */
const uint8_t CRYPTO_AES_KEY[CRYPTO_AES_KEY_LENGTH] = {{
{aes_key_bytes}
}};

/* Klucz HMAC (32 bajty dla SHA-256) */
const uint8_t CRYPTO_HMAC_KEY[CRYPTO_HMAC_KEY_LENGTH] = {{
{hmac_key_bytes}
}};

/* Wektor inicjalizacyjny IV */
const uint8_t CRYPTO_IV[CRYPTO_IV_LENGTH] = {{
{iv_bytes}
}};
"""

# --- Inne Ustawienia ---
DEFAULT_EVENT_LIMIT = 50
MAX_EVENT_LIMIT = 1000
BARRIER_COMMAND_TIMEOUT = 15.0 # Sekundy