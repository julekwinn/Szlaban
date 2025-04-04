# Przewodnik Uruchomienia Systemu ESZP

Cześć!

Oto instrukcja krok po kroku, jak uruchomić system Elektronicznego Szlabanu Zdalnie Programowalnego (ESZP) u siebie. System składa się z dwóch głównych części:

1.  **API Centrala:** Serwer działający na Twoim **laptopie** (Windows/Linux/macOS), który zarządza użytkownikami, szlabanami, uprawnieniami i zbiera logi zdarzeń. Działa na porcie **5002**.
2.  **System Szlabanu:** Aplikacja działająca na **Raspberry Pi (RPi)**, która bezpośrednio steruje fizycznym szlabanem (lub jego symulacją), odbiera sygnały radiowe i komunikuje się z API Centralą. Działa na porcie **5000**.

Zakładam, że masz już pobrane oba foldery: `API_CENTRALA` i `SZLABAN`, zgodnie ze strukturą na obrazku.

---

## Część 1: Uruchomienie API Centrali (na Twoim Laptopie)

Ta część będzie działać jako serwer zarządzający na porcie **5002**.

**Krok 1: Przygotowanie środowiska**

1.  Upewnij się, że masz zainstalowanego **Pythona 3** na swoim laptopie. Sprawdź wersję, wpisując `python --version` lub `python3 --version` w terminalu/konsoli.
2.  Otwórz folder `API_CENTRALA` w terminalu (Wiersz Poleceń, PowerShell, terminal Linux/macOS) lub Eksploratorze Plików.

**Krok 2: Instalacja i uruchomienie (za pomocą `start_centrala.bat`)**

Masz plik `start_centrala.bat`, który automatyzuje cały proces na Windows:

1.  **Kliknij dwukrotnie** plik `start_centrala.bat`.
2.  Skrypt powinien automatycznie:

    - Przejść do katalogu, w którym się znajduje.
    - Utworzyć (jeśli nie istnieje) wirtualne środowisko Pythona w podfolderze `.venv`.
    - Aktywować to środowisko.
    - Zainstalować potrzebne biblioteki z pliku `requirements.txt` (m.in. `fastapi`, `uvicorn`, `httpx`, `sqlite3`, `passlib`).
    - Uruchomić serwer FastAPI za pomocą `uvicorn` na hoście `0.0.0.0` i porcie **5002**.

    _Jeśli skrypt `.bat` nie zadziała lub używasz innego systemu (Linux/macOS), wykonaj te kroki ręcznie w terminalu w folderze `API_CENTRALA`:_

    ```bash
    # Przejdź do folderu
    cd /sciezka/do/API_CENTRALA

    # Utwórz środowisko wirtualne (tylko raz)
    python3 -m venv .venv
    # lub 'python -m venv .venv'

    # Aktywuj środowisko (Linux/macOS)
    source .venv/bin/activate
    # Aktywuj środowisko (Windows PowerShell)
    # .\.venv\Scripts\Activate.ps1
    # Aktywuj środowisko (Windows CMD)
    # .\.venv\Scripts\activate.bat

    # Zainstaluj zależności
    pip install -r requirements.txt

    # Uruchom serwer (zgodnie z plikiem .bat)
    uvicorn central_server_fastapi:app --reload --host 0.0.0.0 --port 5002
    ```

3.  Po uruchomieniu powinieneś/powinnaś zobaczyć w konsoli logi informujące, że serwer działa, np. na adresie `http://0.0.0.0:5002`.

**Krok 3: Konfiguracja API Centrali**

Najważniejsze ustawienia znajdują się bezpośrednio w pliku `central_server_fastapi.py`:

- `DATABASE_FILE = "eszp.db"`: Nazwa pliku bazy danych SQLite. Przechowuje dane o użytkownikach, szlabanach, uprawnieniach i zdarzeniach. Tworzy się automatycznie.
- `ADMIN_API_KEY = "ultra-tajny-admin-token-eszp-123"`: Sekretny klucz API do operacji administracyjnych. Potrzebny w nagłówku `X-Admin-API-Key`.
- `LOG_LEVEL = logging.INFO`: Poziom logowania.

**Krok 4: Dostęp do dokumentacji API (Swagger UI)**

FastAPI automatycznie generuje interaktywną dokumentację API.

1.  Otwórz przeglądarkę internetową.
2.  Wejdź na adres `http://127.0.0.1:5002/docs` (lub `http://localhost:5002/docs`).
3.  Zobaczysz interfejs Swagger UI, gdzie możesz:
    - Przeglądać wszystkie dostępne endpointy API.
    - Sprawdzać wymagane dane dla każdego endpointu.
    - Testować endpointy bezpośrednio z przeglądarki.

**Co możesz zrobić przez API Centrali (przykłady z dokumentacji `/docs`):**

- **Endpointy Admina (wymagają `X-Admin-API-Key`):**
  - `POST /api/users`: Stworzyć użytkownika (nazwa, hasło).
  - `POST /api/barriers`: Zarejestrować nowy szlaban (`barrier_id`, `controller_url` RPi).
  - `POST /api/permissions`: Nadać użytkownikowi (`username`) uprawnienia (`operator` / `technician`) do szlabanu (`barrier_id`).
  - `GET /api/events`: Pobrać listę wszystkich zdarzeń.
- **Endpointy Użytkownika (wymagają logowania Basic Auth):**
  - `POST /api/barriers/{barrier_id}/open`: Otworzyć szlaban.
  - `POST /api/barriers/{barrier_id}/close`: Zamknąć szlaban.
  - `POST /api/barriers/{barrier_id}/service/start`: Włączyć tryb serwisowy (`technician`).
  - `POST /api/barriers/{barrier_id}/service/end`: Wyłączyć tryb serwisowy (`technician`).
  - `GET /api/my/barriers`: Pobrać listę swoich szlabanów.
  - `GET /api/my/events`: Pobrać zdarzenia ze swoich szlabanów.
- **Endpoint Odbioru Zdarzeń:**
  - `POST /barrier/event`: Używany przez RPi do wysyłania zdarzeń do Centrali.

---

## Część 2: Uruchomienie Systemu Szlabanu (na Twoim Raspberry Pi)

Ta część będzie działać na RPi i sterować szlabanem, nasłuchując na porcie **5000**.

**Krok 1: Przygotowanie środowiska na RPi**

1.  Upewnij się, że na RPi jest zainstalowany **Python 3** i masz dostęp do terminala (np. przez SSH).
2.  Skopiuj cały folder `SZLABAN` na Raspberry Pi.
3.  Otwórz terminal na RPi i przejdź do skopiowanego folderu `SZLABAN` (`cd /sciezka/do/SZLABAN`).

**Krok 2: Instalacja i uruchomienie (za pomocą `start.sh`)**

Masz plik `start.sh`, który ułatwia proces:

1.  Nadaj uprawnienia do wykonania skryptu (jeśli potrzeba):
    ```bash
    chmod +x start.sh
    ```
2.  Uruchom skrypt:
    ```bash
    ./start.sh
    ```
3.  Skrypt `start.sh` powinien:

    - Sprawdzić/utworzyć wirtualne środowisko `.venv`.
    - Aktywować środowisko.
    - Zainstalować potrzebne biblioteki z `requirements.txt` (m.in. `Flask`, `requests`, `rich`, biblioteki do GPIO, radia, czujnika).
    - Uruchomić główny skrypt kontrolera (np. `python3 main.py`).

4.  W konsoli RPi powinieneś/powinnaś zobaczyć logi startu systemu szlabanu i serwera API (Flask) nasłuchującego na porcie **5000**.

**Krok 3: Konfiguracja Systemu Szlabanu**

Kluczowe ustawienia znajdują się w pliku `main.py` (wewnątrz klasy `AppConfig`):

- `API_HOST = '0.0.0.0'`: Host dla API Flask na RPi (OK).
- `API_PORT = 5000`: Port dla API Flask na RPi (OK).
- `RADIO_MODE = RadioMode.FSK`: Tryb radia.
- `AUTO_CLOSE_DELAY = 10.0`: Czas do auto-zamknięcia (w sekundach).
- `LOG_LEVEL = "INFO"`: Poziom logowania RPi.
- `CENTRAL_ENDPOINT_URL = 'http://192.168.1.101:5002/barrier/event'` **<- BARDZO WAŻNE!**
  - To adres, pod który RPi wysyła powiadomienia do Centrali na laptopie.
  - **MUSISZ** zastąpić `192.168.1.101` **aktualnym adresem IP Twojego laptopa** w Twojej sieci lokalnej (sprawdź przez `ipconfig` / `ip addr`).
  - **Port `5002` jest teraz poprawny**, bo Centrala działa na tym porcie.
  - Jeśli zostawisz `None`, powiadomienia nie będą wysyłane.
- `BARRIER_ID = "szlaban_juliuszka"`: **Unikalny identyfikator tego szlabanu.** Musi być taki sam, jak ten zarejestrowany w Centrali.

**Jak działa System Szlabanu (w skrócie):**

- Odbiera sygnały radiowe (jeśli skonfigurowane) do otwarcia.
- Uruchamia API Flask na porcie `5000` do zdalnego sterowania (`/status`, `/open`, `/close`, `/service/start`, `/service/end`).
- Wysyła powiadomienia o zdarzeniach (start, otwarcie, zamknięcie, błędy) na `CENTRAL_ENDPOINT_URL` (do Centrali).
- Automatycznie zamyka się po `AUTO_CLOSE_DELAY` (jeśli otwarty i nie w trybie serwisowym).
- Loguje działania do konsoli/pliku `szlaban.log`.

---

## Część 3: Łączenie Wszystkiego Razem

Aby system działał jako całość:

1.  **Sieć:** Laptop i RPi muszą być w tej samej sieci lokalnej.
2.  **IP Laptopa:** Znajdź adres IP laptopa i **poprawnie skonfiguruj `CENTRAL_ENDPOINT_URL`** w pliku `main.py` na RPi (z właściwym IP i portem **5002**). Zapisz zmiany.
3.  **IP RPi:** Znajdź adres IP Raspberry Pi (np. komendą `ip addr`).
4.  **Uruchom API Centralę** na laptopie (`start_centrala.bat` lub ręcznie `uvicorn ... --port 5002`).
5.  **Uruchom System Szlabanu** na RPi (`./start.sh`). Sprawdź logi na RPi pod kątem błędów połączenia z Centralą.
6.  **Zarejestruj Szlaban w Centrali:**
    - Otwórz dokumentację API Centrali w przeglądarce: `http://<IP_LAPTOPA>:5002/docs`.
    - Użyj endpointu `POST /api/barriers`.
    - W nagłówku `X-Admin-API-Key` podaj klucz: `ultra-tajny-admin-token-eszp-123`.
    - W ciele zapytania podaj `barrier_id` (np. `"szlaban_juliuszka"`) i `controller_url` (adres RPi, np. `"http://<IP_RPi>:5000"`). Kliknij "Execute".
7.  **(Opcjonalnie) Stwórz użytkownika i nadaj mu uprawnienia:**
    - W dokumentacji API Centrali użyj `POST /api/users` (z kluczem admina), aby stworzyć użytkownika.
    - Użyj `POST /api/permissions` (z kluczem admina), aby nadać mu uprawnienia do szlabanu.
8.  **Testuj!**
    - Wyślij polecenie otwarcia z dokumentacji API Centrali (`POST /api/barriers/szlaban_juliuszka/open`). Pamiętaj o autoryzacji (przycisk "Authorize", podaj dane użytkownika).
    - Obserwuj logi na RPi (powinno przyjść żądanie) i na laptopie (powinno przyjść zdarzenie `barrier_opened`).

---

Mam nadzieję, że ta wersja jest pomocna! Powodzenia!
