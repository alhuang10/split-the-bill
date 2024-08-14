#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Define the name of the virtual environment directory
VENV_DIR=".venv"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3 and try again."
    exit 1
fi

# Remove existing virtual environment if it's corrupted
if [ -d "$VENV_DIR" ]; then
    if [ ! -f "$VENV_DIR/bin/activate" ]; then
        echo "Existing virtual environment is corrupted. Removing it..."
        rm -rf "$VENV_DIR"
    fi
fi
# Create a virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists."
fi

# Activate the virtual environment
source "$VENV_DIR/bin/activate"

# Upgrade pip
pip3 install --upgrade pip

# Install requirements if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "Installing requirements..."
    pip3 install -r requirements.txt
else
    echo "requirements.txt not found. Skipping package installation."
fi

echo "Setup complete. You can now activate the virtual environment with:"
echo "source $VENV_DIR/bin/activate"