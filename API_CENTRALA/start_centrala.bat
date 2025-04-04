@echo off
:: Skrypt .bat do konfiguracji środowiska i uruchamiania serwera Centrali ESZP (FastAPI)
:: 1. Sprawdza/tworzy środowisko wirtualne .venv
:: 2. Aktywuje środowisko wirtualne
:: 3. Instaluje/aktualizuje zależności z requirements.txt
:: 4. Uruchamia serwer Uvicorn
:: 5. Pozostawia okno konsoli otwarte po zatrzymaniu serwera.

title Centrala ESZP Server Setup & Run

echo Konfiguracja i uruchamianie serwera Centrali ESZP...
echo.

REM ==========================================================================
REM Krok 0: Przejście do katalogu skryptu
REM ==========================================================================
REM Upewniamy się, że działamy w folderze, gdzie jest ten plik .bat
cd /d "%~dp0"
echo Katalog roboczy: %cd%
echo.

REM ==========================================================================
REM Krok 1: Środowisko Wirtualne (.venv)
REM ==========================================================================
echo === Krok 1: Sprawdzanie/Tworzenie srodowiska wirtualnego (.venv) ===
set VENV_DIR=.\.venv

if not exist "%VENV_DIR%\" (
    echo Srodowisko '%VENV_DIR%' nie istnieje. Proba utworzenia...
    REM Wymaga, aby 'python' (lub 'py') był w systemowym PATH
    python -m venv %VENV_DIR%
    if %errorlevel% neq 0 (
        echo.
        echo BLAD KRYTYCZNY: Nie udalo sie utworzyc srodowiska wirtualnego '%VENV_DIR%'!
        echo Sprawdz, czy komenda 'python -m venv .venv' dziala poprawnie w tym katalogu.
        echo Upewnij sie, ze Python jest zainstalowany i dostepny w PATH.
        echo.
        pause
        exit /b %errorlevel%
    )
    echo Srodowisko '%VENV_DIR%' utworzone pomyslnie.
) else (
    echo Srodowisko '%VENV_DIR%' juz istnieje.
)
echo.

REM ==========================================================================
REM Krok 2: Aktywacja Środowiska Wirtualnego
REM ==========================================================================
echo === Krok 2: Aktywacja srodowiska wirtualnego ===
set VENV_ACTIVATE_SCRIPT=%VENV_DIR%\Scripts\activate.bat

if not exist "%VENV_ACTIVATE_SCRIPT%" (
    echo.
    echo BLAD KRYTYCZNY: Nie znaleziono skryptu aktywacyjnego: %VENV_ACTIVATE_SCRIPT%
    echo Srodowisko '%VENV_DIR%' moze byc uszkodzone lub niekompletne.
    echo Sprobuj usunac folder '%VENV_DIR%' i uruchomic ten skrypt ponownie.
    echo.
    pause
    exit /b 1
)

echo Aktywacja: %VENV_ACTIVATE_SCRIPT%
call "%VENV_ACTIVATE_SCRIPT%"
if %errorlevel% neq 0 (
    echo.
    echo BLAD: Aktywacja srodowiska wirtualnego nie powiodla sie.
    echo.
    pause
    exit /b %errorlevel%
)
echo Srodowisko wirtualne powinno byc aktywne.
echo.

REM ==========================================================================
REM Krok 3: Instalacja Zależności
REM ==========================================================================
echo === Krok 3: Instalacja/Aktualizacja zaleznosci z requirements.txt ===
if not exist requirements.txt (
    echo.
    echo BLAD KRYTYCZNY: Brak pliku requirements.txt w katalogu %cd%!
    echo Nie mozna zainstalowac potrzebnych bibliotek. Utworz plik requirements.txt.
    echo.
    pause
    exit /b 1
)

echo Znaleziono requirements.txt. Uruchamianie pip install...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo BLAD: Instalacja zaleznosci z requirements.txt nie powiodla sie.
    echo Sprawdz polaczenie internetowe, poprawnosc pliku requirements.txt
    echo oraz komunikaty bledow powyzej.
    echo.
    pause
    exit /b %errorlevel%
)
echo Zaleznosci zainstalowane/zaktualizowane pomyslnie.
echo.

REM ==========================================================================
REM Krok 4: Uruchomienie Serwera FastAPI
REM ==========================================================================
echo === Krok 4: Uruchamianie serwera FastAPI (Uvicorn) ===
echo Plik Pythona: central_server_fastapi.py
echo Obiekt aplikacji: app
echo Host: 0.0.0.0
echo Port: 5002
echo Tryb reload: wlaczony
echo.
echo Nacisnij Ctrl+C w tym oknie, aby zatrzymac serwer.
echo.

uvicorn central_server_fastapi:app --reload --host 0.0.0.0 --port 5002

REM ==========================================================================
REM Zakończenie
REM ==========================================================================
REM 'pause' utrzymuje okno otwarte po zatrzymaniu serwera (Ctrl+C)
REM lub w przypadku błędu startu Uvicorn.
echo.
echo Serwer Uvicorn zostal zatrzymany lub wystapil blad krytyczny podczas uruchamiania.
pause