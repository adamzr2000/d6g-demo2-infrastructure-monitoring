#!/bin/bash

# Check for --local-ip argument
if [[ "$1" != "--local-ip" || -z "$2" ]]; then
    echo "Usage: $0 --local-ip <IP_ADDRESS>"
    exit 1
fi

LOCAL_IP=$2

echo "Starting infrastructure monitoring..."

# Call start_edge.sh with IP
echo "Starting edge stack with IP: $LOCAL_IP"
EDGE_SCRIPT_DIR="$(dirname "$0")/edge"
cd "$EDGE_SCRIPT_DIR" || { echo "Failed to enter $EDGE_SCRIPT_DIR. Exiting."; exit 1; }
./start_edge.sh --local-ip "$LOCAL_IP"

# Sleep to allow edge stack to initialize
echo "Waiting 10 seconds for edge services to initialize..."
sleep 10

cd ..  # Go back to root project directory

# Overwrite kafkaIP in config files
CONFIG_DIR="$(dirname "$0")/producer-consumer/config"
echo "Updating kafkaIP and influxdb_url in all config files to: $LOCAL_IP"
for file in "$CONFIG_DIR"/*.conf; do
    sed -i "s/^kafkaIP = .*/kafkaIP = ${LOCAL_IP}/" "$file"
    sed -i "s|^influxdb_url = .*|influxdb_url = http://${LOCAL_IP}:8088|" "$file"
done

# Navigate to the producer-consumer directory
SCRIPT_DIR="$(dirname "$0")/producer-consumer"
echo "Changing directory to: $SCRIPT_DIR"
cd "$SCRIPT_DIR" || { echo "Failed to change directory to $SCRIPT_DIR. Exiting."; exit 1; }

# Start kafka_producer.py in a detached screen session with sudo password input
echo "Starting Kafka Producer in a screen session..."
screen -dmS kafka_producer bash -c "echo 'Starting kafka_producer.py...'; \
    sudo -S -E /home/desire6g/.pyenv/versions/3.10.12/bin/python3 kafka_producer.py --file config/configP1.conf < /home/desire6g/.sudo_pass; \
    echo 'Kafka Producer stopped.'"

# Give some time for Kafka Producer to initialize
sleep 2
screen -list | grep kafka_producer && echo "Kafka Producer started successfully." || echo "Failed to start Kafka Producer."

# Start run_kafka_agent.sh with specified arguments
echo "Starting Kafka-to-InfluxDB agent..."
if ./run_kafka_agent.sh --script kafka_to_influx.py --file-name configCInfluxDB.conf; then
    echo "Kafka-to-InfluxDB agent started successfully."
else
    echo "Failed to start Kafka-to-InfluxDB agent."
fi

echo "Infrastructure monitoring setup complete."
