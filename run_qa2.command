#!/bin/bash
# macOS. Same two ways of starting as run_qa2.bat: a bundled Python if
# this folder is the package handed to the team, otherwise the system
# Python and a .venv.
cd "$(dirname "$0")" || exit 1

if [ -x "python/bin/python3" ]; then
    export PLAYWRIGHT_BROWSERS_PATH="$PWD/browsers"
    echo "Starting QA2. Your browser will open automatically."
    echo "Keep this window open while you work - closing it stops QA2."
    exec ./python/bin/python3 -m streamlit run ui/app_v2.py
fi

if [ ! -d .venv ]; then
    echo "Setting up QA2 for the first time, this can take a minute..."
    python3 -m venv .venv || exit 1
fi

source .venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo "Starting QA2. Your browser will open automatically."
exec python -m streamlit run ui/app_v2.py
