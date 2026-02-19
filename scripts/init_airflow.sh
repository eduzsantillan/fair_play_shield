#!/bin/bash

set -e

echo "=============================================="
echo "Fair Play Shield - Airflow + MLflow Setup"
echo "=============================================="

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [ ! -f ".env" ]; then
    echo "[1/5] Creating .env file from .env.example..."
    cp .env.example .env
    echo "AIRFLOW_UID=$(id -u)" >> .env
else
    echo "[1/5] .env file already exists"
fi

echo "[2/5] Creating required directories..."
mkdir -p airflow/dags airflow/logs airflow/plugins
mkdir -p data/raw data/processed
mkdir -p models/trained

echo "[3/5] Setting permissions..."
chmod -R 777 airflow/logs || true

echo "[4/5] Building Docker images..."
docker-compose build

echo "[5/5] Starting services..."
docker-compose up -d

echo ""
echo "=============================================="
echo "Setup complete!"
echo "=============================================="
echo ""
echo "Services:"
echo "  - Airflow UI:  http://localhost:8080  (user: airflow, pass: airflow)"
echo "  - MLflow UI:   http://localhost:5001"
echo "  - PostgreSQL:  localhost:5432"
echo ""
echo "Commands:"
echo "  docker-compose logs -f              # View logs"
echo "  docker-compose down                 # Stop all services"
echo "  docker-compose up -d                # Start all services"
echo ""
echo "Trigger pipeline manually:"
echo "  docker exec airflow-scheduler airflow dags trigger fps_pipeline"
echo ""
