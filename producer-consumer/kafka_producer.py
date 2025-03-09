import argparse
import json
import logging
import sys
import time
import psutil
from ping3 import ping
from kafkaConnections import kafkaConnections
from confluent_kafka import Producer
import threading

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

# Argument Parser
parser = argparse.ArgumentParser(description="Kafka System Metrics Producer")
parser.add_argument('--file', dest='file', default="configP1.conf", help="Configuration file")
args = parser.parse_args()

# Kafka Initialization
try:
    ec = kafkaConnections(args.file)
    topic = ec.ktopic
    producer = ec.createKafkaProducer()
    ec.createKafkaTopic(topic)
except Exception as e:
    log.error(f"Failed to initialize Kafka: {e}")
    sys.exit(1)

# Ping Targets with Named Keys
ping_targets = {
    "google-dns": "8.8.8.8",
    "cloudflare-dns": "1.1.1.1",
    "quad9-dns": "9.9.9.9"
}

# Store ping results per target
ping_results = {name: {"total": 0, "success": 0, "failure": 0, "latest_latency": None} for name in ping_targets}

def update_ping(target_name, target_ip):
    """Continuously pings the target IP and records latency & loss."""
    while True:
        try:
            latency = ping(target_ip, timeout=1)
            ping_results[target_name]["total"] += 1
            if latency is not None:
                ping_results[target_name]["success"] += 1
                ping_results[target_name]["latest_latency"] = round(latency * 1000, 2)  # Convert to ms
            else:
                ping_results[target_name]["failure"] += 1
        except Exception as e:
            log.warning(f"Ping error for {target_name} ({target_ip}): {e}")
            ping_results[target_name]["failure"] += 1
        time.sleep(1)  # Ping every second

def get_system_metrics():
    """Collects system metrics and formats ping results."""
    # CPU & Memory Metrics (Grouped)
    system_metrics = {
        "cpu_usage_percent": round(psutil.cpu_percent(interval=1), 2),
        "ram_usage_percent": round(psutil.virtual_memory().percent, 2),
        "total_ram_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
        "free_ram_gb": round(psutil.virtual_memory().available / (1024 ** 3), 2)
    }

    # Network Metrics (Formatted)
    ping_data = {}
    for name, ip in ping_targets.items():
        total_pings = ping_results[name]["total"] or 1  # Avoid division by zero
        packet_loss = round((ping_results[name]["failure"] / total_pings) * 100, 2)

        ping_data[name] = {
            "ip": ip,
            "latency_ms": ping_results[name]["latest_latency"],
            "packet_loss_percent": packet_loss,
            "total_pings": ping_results[name]["total"],
            "successful_pings": ping_results[name]["success"],
            "failed_pings": ping_results[name]["failure"]
        }

    return {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "site_id": "D6Gsite1",
        "system_metrics": system_metrics,  
        "network_metrics": ping_data  
    }

def delivery_callback(err, msg):
    """Handles Kafka message delivery confirmation."""
    if err:
        log.error(f"Message delivery failed: {err}")
    else:
        log.info(f"Message delivered to {msg.topic()} [Partition {msg.partition()}] @ Offset {msg.offset()}")

# Start Ping Monitoring in Background Threads
for name, ip in ping_targets.items():
    threading.Thread(target=update_ping, args=(name, ip), daemon=True).start()

# Main Kafka Producer Loop
try:
    while True:
        metrics = get_system_metrics()
        message = json.dumps(metrics, indent=4)
        producer.produce(topic, value=message, callback=delivery_callback)
        producer.poll(0)  # Trigger Kafka delivery callbacks
        
        log.info("[METRICS UPDATE]\n" + json.dumps(metrics, indent=4))
        time.sleep(2)  # Adjust reporting interval
except KeyboardInterrupt:
    log.info("Kafka Producer Stopped.")
finally:
    producer.flush()
