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
import socket
import docker

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

# Ping Targets
ping_targets = {
    "google-dns": "8.8.8.8",
    "cloudflare-dns": "1.1.1.1",
    "5tonic-gw": "10.5.0.1",
    "gNB": "10.5.15.49"
}

ping_results = {name: {"total": 0, "success": 0, "failure": 0, "latest_latency": None} for name in ping_targets}

# Docker metrics cache
docker_metrics_cache = []
docker_metrics_lock = threading.Lock()

def update_ping(target_name, target_ip):
    """Continuously pings the target IP and records latency & loss."""
    while True:
        try:
            latency = ping(target_ip, timeout=1)
            ping_results[target_name]["total"] += 1
            if latency is not None:
                ping_results[target_name]["success"] += 1
                ping_results[target_name]["latest_latency"] = round(latency * 1000, 2)
            else:
                ping_results[target_name]["failure"] += 1
        except Exception as e:
            log.warning(f"Ping error for {target_name} ({target_ip}): {e}")
            ping_results[target_name]["failure"] += 1
        time.sleep(1)

def get_docker_metrics():
    """Collects metrics from all running Docker containers."""
    docker_metrics = []
    try:
        client = docker.from_env()
        containers = client.containers.list(filters={"status": "running"})
        for container in containers:
            try:
                stats = container.stats(stream=False)
                mem_stats = stats['memory_stats']
                cpu_stats = stats['cpu_stats']
                precpu_stats = stats['precpu_stats']

                cpu_delta = cpu_stats['cpu_usage']['total_usage'] - precpu_stats['cpu_usage']['total_usage']
                system_delta = cpu_stats['system_cpu_usage'] - precpu_stats['system_cpu_usage']
                percpu = cpu_stats['cpu_usage'].get('percpu_usage')
                num_cpus = len(percpu) if percpu else 1
                cpu_percent = (cpu_delta / system_delta) * num_cpus * 100.0 if system_delta > 0 else 0.0

                net_rx = 0
                net_tx = 0
                if 'networks' in stats:
                    for iface in stats['networks'].values():
                        net_rx += iface.get('rx_bytes', 0)
                        net_tx += iface.get('tx_bytes', 0)

                docker_metrics.append({
                    "name": container.name,
                    "ram_usage_bytes": mem_stats.get('usage', 0),
                    "cpu_usage_percent": round(cpu_percent, 2),
                    "net_rx_bytes": net_rx,
                    "net_tx_bytes": net_tx
                })
            except Exception as e:
                log.warning(f"Failed to get stats for container {container.name}: {e}")
    except Exception as e:
        log.warning(f"Docker not available or error fetching container stats: {e}")
    return docker_metrics

def docker_metrics_updater():
    """Background thread to periodically update docker metrics."""
    global docker_metrics_cache
    while True:
        updated_metrics = get_docker_metrics()
        with docker_metrics_lock:
            docker_metrics_cache = updated_metrics
        time.sleep(10)

def get_system_metrics():
    vmem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    cpu_times = psutil.cpu_times_percent(interval=1, percpu=False)

    with docker_metrics_lock:
        docker_data = docker_metrics_cache.copy()

    system_metrics = {
        "hostname": socket.gethostname(),
        "uptime_seconds": time.time() - psutil.boot_time(),
        "cpu_usage_percent": round(psutil.cpu_percent(interval=None), 2),
        "cpu_logical_cores": psutil.cpu_count(logical=True),
        "cpu_physical_cores": psutil.cpu_count(logical=False),
        "cpu_user_percent": round(cpu_times.user, 2),
        "cpu_system_percent": round(cpu_times.system, 2),
        "cpu_idle_percent": round(cpu_times.idle, 2),
        "cpu_iowait_percent": round(getattr(cpu_times, 'iowait', 0.0), 2),
        "cpu_irqs_percent": round(
            getattr(cpu_times, 'irq', 0.0) + getattr(cpu_times, 'softirq', 0.0), 2
        ),
        "ram_usage_percent": round(vmem.percent, 2),
        "ram_total_bytes": vmem.total,
        "ram_used_bytes": vmem.used,
        "ram_free_bytes": vmem.free,
        "ram_reclaimable_bytes": (
            (getattr(vmem, "cached", 0) or 0) +
            (getattr(vmem, "buffers", 0) or 0)
        ),
        "swap_usage_percent": round(swap.percent, 2),
        "swap_total_bytes": swap.total,
        "swap_used_bytes": swap.used,
        "swap_free_bytes": swap.free,
    }

    ping_data = {}
    for name, ip in ping_targets.items():
        total_pings = ping_results[name]["total"] or 1
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
        "ping_metrics": ping_data,
        "docker_metrics": {
            "docker_container_count": len(docker_data),
            "containers": docker_data
        }
    }

def delivery_callback(err, msg):
    if err:
        log.error(f"Message delivery failed: {err}")
    else:
        log.info(f"Message delivered to {msg.topic()} [Partition {msg.partition()}] @ Offset {msg.offset()}")

# Start ping and docker updater threads
for name, ip in ping_targets.items():
    threading.Thread(target=update_ping, args=(name, ip), daemon=True).start()

threading.Thread(target=docker_metrics_updater, daemon=True).start()

# Main Kafka Producer Loop
try:
    while True:

        metrics = get_system_metrics()
        message = json.dumps(metrics, separators=(",", ":"))
        producer.produce(topic, value=message, callback=delivery_callback)
        producer.poll(0)

        log.info(f"[METRICS] {metrics['time']} | Host: {metrics['system_metrics']['hostname']}")
        time.sleep(5)
except KeyboardInterrupt:
    log.info("Kafka Producer Stopped.")
finally:
    producer.flush()
