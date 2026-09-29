#!/usr/bin/env bash
# Runs on Render.com every time you deploy (Build Command: bash build.sh)
set -o errexit

pip install -r requirements-prod.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput

# First deploy only: sample routes (your admin changes are kept on later deploys)
python manage.py load_sample_data --if-empty

# Admin account from the DJANGO_SUPERUSER_USERNAME / DJANGO_SUPERUSER_PASSWORD settings (first deploy only)
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  if python manage.py shell -c "import os, sys; from django.contrib.auth import get_user_model; sys.exit(0 if get_user_model().objects.filter(username=os.environ['DJANGO_SUPERUSER_USERNAME']).exists() else 1)"; then
    echo "Admin account already exists."
  else
    python manage.py createsuperuser --noinput --email "${DJANGO_SUPERUSER_EMAIL:-admin@example.com}"
  fi
fi

# Road paths for the map (needs internet; the site still works if this fails)
python manage.py fetch_road_paths || echo "Road paths will download later."
