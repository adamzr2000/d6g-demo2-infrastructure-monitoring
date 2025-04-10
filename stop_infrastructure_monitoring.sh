#!/bin/bash

echo "Stopping Kafka Producer screen session..."
screen -S kafka_producer -XS quit

echo "Stopping kafka_to_influx Docker container..."
docker ps -q --filter "name=kafka_to_influx" | xargs -r docker kill

echo "Stopping edge stack..."
EDGE_SCRIPT_DIR="$(dirname "$0")/edge"
cd "$EDGE_SCRIPT_DIR" || { echo "Failed to enter $EDGE_SCRIPT_DIR. Exiting."; exit 1; }
./stop_edge.sh

echo "Infrastructure monitoring stopped."