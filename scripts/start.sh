#!/bin/bash

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "AIRFLOW_UID=$(id -u)" >> .env
fi

mkdir -p airflow/dags airflow/logs airflow/plugins
mkdir -p data/raw data/processed
mkdir -p models/trained

chmod -R 777 airflow/logs 2>/dev/null || true

echo "Starting services..."
docker-compose up -d

echo ""
echo "Services ready:"
echo "  Airflow:   http://localhost:8080  (airflow / airflow)"
echo "  MLflow:    http://localhost:5001"
echo "  Dashboard: http://localhost:8050"
echo ""
echo "Trigger pipeline manually:"
echo "  docker exec airflow-scheduler airflow dags trigger fps_pipeline"
echo ""
echo "Stop all services:"
echo "  bash scripts/stop_services.sh"
