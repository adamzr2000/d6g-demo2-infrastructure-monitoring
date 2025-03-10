#!/bin/bash

echo "Stopping Kafka Producer screen session..."
screen -S kafka_producer -XS quit

echo "Stopping kafka_to_influx Docker container..."
docker ps -q --filter "name=kafka_to_influx" | xargs -r docker kill

echo "Infrastructure monitoring stopped."