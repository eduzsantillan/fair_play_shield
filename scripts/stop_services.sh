#!/bin/bash

echo "Stopping Fair Play Shield services..."

cd "$(dirname "${BASH_SOURCE[0]}")/.."

docker-compose down

echo "All services stopped."
