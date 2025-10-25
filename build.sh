#!/usr/bin/env bash
# Exit on error
set -o errexit

# Create a virtual environment (Render will use this)
python -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --no-input