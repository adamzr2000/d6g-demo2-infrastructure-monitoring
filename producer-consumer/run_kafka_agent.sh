#!/bin/bash

# Ensure required arguments are provided
if [ "$#" -ne 4 ] || [ "$1" != "--script" ] || [ "$3" != "--file-name" ]; then
    echo "Usage: $0 --script <script_name.py> --file-name <config_file.conf>"
    echo "Example: $0 --script kafka_consumer.py --file-name configC1.conf"
    exit 1
fi

SCRIPT_NAME="$2"  # Extract script name
CONFIG_FILE="$4"  # Extract config file
CONTAINER_NAME="${SCRIPT_NAME%.py}"  # Remove .py extension for container name

echo "Running Kafka Agent: $SCRIPT_NAME with config: $CONFIG_FILE in container: $CONTAINER_NAME"

docker run -d --rm \
    --name "$CONTAINER_NAME" \
    --net host \
    -v "./config:/app/config" \
    -v "./kafka_consumer.py:/app/kafka_consumer.py" \
    -v "./kafka_producer.py:/app/kafka_producer.py" \
    -v "./kafka_to_influx.py:/app/kafka_to_influx.py" \
    -v "./kafkaConnections.py:/app/kafkaConnections.py" \
    kafka-agent:latest \
    "$SCRIPT_NAME" --file "/app/config/$CONFIG_FILE"
