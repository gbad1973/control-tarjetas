#!/usr/bin/env bash
# Salir si algún comando falla
set -e

echo "Instalando dependencias..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Ejecutando migraciones..."
python manage.py migrate --noinput

echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

echo "Build completado con éxito."