#!/bin/bash
set -e

echo "=========================================="
echo "REINSTALLING REQUIREMENTS"
echo "=========================================="
cd /Users/Daniel/Desktop/code/simbyp-email-notifications
source venv/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing requirements..."
pip install -r requirements.txt

echo ""
echo "=========================================="
echo "RUNNING SETUP TEST"
echo "=========================================="
python test_setup.py
