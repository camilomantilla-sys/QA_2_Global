#!/bin/bash
set -e

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "Setting up QA2 for the first time, this can take a minute..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "Checking required packages..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo ""
echo "Starting QA2. Your browser will open automatically."
echo "Keep this window open while you work - closing it stops QA2."
echo ""

python -m streamlit run ui/app_v2.py
