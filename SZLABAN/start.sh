#!/bin/bash
# Prostszy skrypt do konfiguracji srodowiska i uruchomienia aplikacji Flask

# Zakoncz dzialanie skryptu, jesli jakikolwiek polecenie zwroci blad
set -e 

echo "--- Uruchamianie Kontrolera Bariery ---"

# Linia 10: Ustalenie katalogu skryptu
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)" 
# Linia 11: Przejscie do katalogu skryptu
cd "$SCRIPT_DIR"
echo "Katalog roboczy: $SCRIPT_DIR"

# --- 1 & 2. Srodowisko Wirtualne ---
VENV_DIR=".venv"
VENV_ACTIVATE="$VENV_DIR/bin/activate"

if [ ! -d "$VENV_DIR" ]; then
    echo "Tworzenie srodowiska wirtualnego '$VENV_DIR'..."
    python3 -m venv "$VENV_DIR" 
fi

echo "Aktywacja srodowiska wirtualnego..."
# Sprawdz, czy plik aktywacyjny istnieje PRZED proba aktywacji
if [ ! -f "$VENV_ACTIVATE" ]; then
    echo "BLAD KRYTYCZNY: Nie znaleziono skryptu aktywacyjnego: $VENV_ACTIVATE"
    echo "Srodowisko '$VENV_DIR' moze byc uszkodzone. Sprobuj je usunac i uruchomic skrypt ponownie."
    exit 1
fi
source "$VENV_ACTIVATE"

# --- 3. Instalacja Zaleznosci ---
REQUIREMENTS_FILE="requirements.txt"
if [ -f "$REQUIREMENTS_FILE" ]; then
    echo "Instalowanie zaleznosci z $REQUIREMENTS_FILE..."
    pip install -r "$REQUIREMENTS_FILE"
else
    echo "Plik '$REQUIREMENTS_FILE' nie znaleziony, pomijanie instalacji zaleznosci."
fi

# --- 4. Uruchomienie Aplikacji ---
MAIN_SCRIPT="main.py"
if [ ! -f "$MAIN_SCRIPT" ]; then
    echo "BLAD KRYTYCZNY: Nie znaleziono glownego skryptu aplikacji: $MAIN_SCRIPT"
    exit 1
fi

echo "Uruchamianie aplikacji ($MAIN_SCRIPT)... Nacisnij Ctrl+C aby zatrzymac." 
python3 "$MAIN_SCRIPT"

# Skrypt zakonczy sie z kodem wyjscia ostatniego polecenia (python3 main.py)
# dzieki 'set -e'
echo "Aplikacja kontrolera bariery zatrzymana."