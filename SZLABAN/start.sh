#!/bin/bash
# Simple script to setup environment and run the Flask barrier controller

echo "=============================================="
echo " Setting up and Running ESZP Barrier Controller "
echo "=============================================="
echo

# Go to the script's directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
if [ $? -ne 0 ]; then
    echo "ERROR: Cannot change directory to $SCRIPT_DIR"
    exit 1
fi
echo "Working directory: $(pwd)"
echo

# --- 1. Virtual Environment (.venv) ---
VENV_DIR=".venv"
echo "--- Step 1: Checking/Creating virtual environment ($VENV_DIR) ---"
if [ ! -d "$VENV_DIR" ]; then
    echo "Environment '$VENV_DIR' not found. Creating..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "CRITICAL ERROR: Failed to create virtual environment '$VENV_DIR'."
        echo "Check if 'python3' and 'venv' module are installed and working."
        exit 1
    fi
    echo "Environment '$VENV_DIR' created successfully."
else
    echo "Environment '$VENV_DIR' already exists."
fi
echo

# --- 2. Activate Virtual Environment ---
VENV_ACTIVATE="$VENV_DIR/bin/activate"
echo "--- Step 2: Activating virtual environment ---"
if [ ! -f "$VENV_ACTIVATE" ]; then
    echo "CRITICAL ERROR: Activation script not found: $VENV_ACTIVATE"
    echo "Environment '$VENV_DIR' might be corrupted. Try removing it and running again."
    exit 1
fi
source "$VENV_ACTIVATE"
echo "Virtual environment activated."
echo

# --- 3. Install Dependencies ---
REQUIREMENTS_FILE="requirements.txt"
echo "--- Step 3: Installing dependencies from $REQUIREMENTS_FILE ---"
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "WARNING: File '$REQUIREMENTS_FILE' not found in $(pwd)."
    echo "Assuming no extra dependencies are needed."
else
    echo "Found $REQUIREMENTS_FILE. Running 'pip install -r $REQUIREMENTS_FILE'..."
    pip install -r "$REQUIREMENTS_FILE"
    if [ $? -ne 0 ]; then
        echo "CRITICAL ERROR: Failed to install dependencies from $REQUIREMENTS_FILE."
        echo "Check network connection, file content, and error messages above."
        exit 1
    fi
    echo "Dependencies installed/updated successfully."
fi
echo

