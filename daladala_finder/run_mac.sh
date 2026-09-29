#!/bin/bash
# Daladala Finder - one-click setup and run on macOS
# (VS Code: Terminal > Run Build Task, or in Terminal: bash run_mac.sh)
set -e
cd "$(dirname "$0")"

if [ ! -d venv ]; then
  echo ">> Creating virtual environment..."
  python3 -m venv venv
fi
source venv/bin/activate

echo ">> Installing Django..."
pip install -q -r requirements.txt

echo ">> Setting up database..."
python manage.py migrate
python manage.py load_sample_data

echo ">> Getting road paths for the map (needs internet, only slow the first time)..."
python manage.py fetch_road_paths || echo "   Could not get all road paths now. The site still works; they will download later."

echo ""
echo ">> Everyone must log in. Open the site and click 'Sign up' to create your account."
echo "   (Admin account: stop the server, then run: python manage.py createsuperuser)"
echo ""
echo ">> Starting server at http://127.0.0.1:8000  (press Ctrl+C to stop)"
(sleep 3 && open http://127.0.0.1:8000) &
python manage.py runserver
