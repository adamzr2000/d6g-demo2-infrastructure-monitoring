import json
import logging
import argparse
from configparser import ConfigParser
from confluent_kafka import Consumer, KafkaException
from influxdb_client import InfluxDBClient, WriteOptions, Point
from influxdb_client.client.write_api import ASYNCHRONOUS

# Configure Logging with timestamps
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

# Parse Command-Line Argument for Config File
parser = argparse.ArgumentParser(description="Kafka Consumer to InfluxDB")
parser.add_argument('--file', type=str, required=True, help='Configuration file')
args = parser.parse_args()

# Load Configuration File
config = ConfigParser()
config.read(args.file)

# Read Kafka Configurations from File
try:
    kafka_ip = config.get("kafka", "kafkaIP")
    kafka_port = config.get("kafka", "kafkaPort")
    kafka_topic = config.get("kafka", "kafkaTopic")
    kafka_group_id = config.get("kafka", "kafkaID")
    log.info(f"Kafka Configurations: IP={kafka_ip}, Port={kafka_port}, Topic={kafka_topic}, GroupID={kafka_group_id}")
except Exception as e:
    log.error(f"Error reading Kafka configuration: {e}")
    exit(1)

# Create Kafka Consumer
consumer_config = {
    'bootstrap.servers': f"{kafka_ip}:{kafka_port}",
    'group.id': kafka_group_id,
    'auto.offset.reset': 'earliest'
}
try:
    consumer = Consumer(consumer_config)
    consumer.subscribe([kafka_topic])
    log.info(f"Successfully connected to Kafka topic: {kafka_topic}")
except KafkaException as e:
    log.error(f"Error initializing Kafka consumer: {e}")
    exit(1)

# Read InfluxDB Configurations from File
try:
    influxdb_url = config.get("influxdb", "influxdb_url")
    influxdb_token = config.get("influxdb", "influxdb_token")
    influxdb_org = config.get("influxdb", "influxdb_org")
    influxdb_bucket = config.get("influxdb", "influxdb_bucket")
    log.info(f"InfluxDB Configurations: URL={influxdb_url}, Org={influxdb_org}, Bucket={influxdb_bucket}")
except Exception as e:
    log.error(f"Error reading InfluxDB configuration: {e}")
    exit(1)

# Initialize InfluxDB Client
try:
    influx_client = InfluxDBClient(url=influxdb_url, token=influxdb_token, org=influxdb_org)
    write_api = influx_client.write_api(write_options=WriteOptions(batch_size=100, flush_interval=2000, write_type=ASYNCHRONOUS))
    log.info(f"Successfully connected to InfluxDB at {influxdb_url}")
except Exception as e:
    log.error(f"Error connecting to InfluxDB: {e}")
    exit(1)

# Function to Consume Kafka Messages and Write to InfluxDB
def consume_messages():
    try:
        log.info("Starting Kafka message consumption...")
        while True:
            msg = consumer.poll(1.0)

            if msg is None:
                continue

            batch = []
            
            if msg.error():
                log.warning(f"Kafka message error: {msg.error()}")
                continue

            try:
                # Parse JSON message
                data = json.loads(msg.value().decode("utf-8"))
                site_id = data.get("site_id", "unknown")

                # SYSTEM METRICS
                if "system_metrics" in data:
                    sm = data["system_metrics"]
                    point = (
                        Point("system_metrics")
                        .tag("site_id", site_id)
                        .tag("hostname", sm.get("hostname", "unknown"))
                        .field("uptime_seconds", sm.get("uptime_seconds", 0))
                        
                        # CPU
                        .field("cpu_usage_percent", sm.get("cpu_usage_percent", 0))
                        .field("cpu_logical_cores", sm.get("cpu_logical_cores", 0))
                        .field("cpu_physical_cores", sm.get("cpu_physical_cores", 0))
                        .field("cpu_user_percent", sm.get("cpu_user_percent", 0))
                        .field("cpu_system_percent", sm.get("cpu_system_percent", 0))
                        .field("cpu_idle_percent", sm.get("cpu_idle_percent", 0))
                        .field("cpu_iowait_percent", sm.get("cpu_iowait_percent", 0))
                        .field("cpu_irqs_percent", sm.get("cpu_irqs_percent", 0))

                        # RAM
                        .field("ram_usage_percent", sm.get("ram_usage_percent", 0))
                        .field("ram_total_bytes", sm.get("ram_total_bytes", 0))
                        .field("ram_used_bytes", sm.get("ram_used_bytes", 0))
                        .field("ram_free_bytes", sm.get("ram_free_bytes", 0))
                        .field("ram_reclaimable_bytes", sm.get("ram_reclaimable_bytes", 0))

                        # SWAP
                        .field("swap_usage_percent", sm.get("swap_usage_percent", 0))
                        .field("swap_total_bytes", sm.get("swap_total_bytes", 0))
                        .field("swap_used_bytes", sm.get("swap_used_bytes", 0))
                        .field("swap_free_bytes", sm.get("swap_free_bytes", 0))
                    )
                    batch.append(point)

                # PING METRICS
                if "ping_metrics" in data:
                    for target_name, ping_info in data["ping_metrics"].items():
                        point = (
                            Point("ping_metrics")
                            .tag("site_id", site_id)
                            .tag("target_name", target_name)
                            .tag("target_ip", ping_info.get("ip", "unknown"))
                            .field("latency_ms", ping_info.get("latency_ms", 0))
                            .field("packet_loss_percent", ping_info.get("packet_loss_percent", 0))
                            .field("total_pings", ping_info.get("total_pings", 0))
                            .field("successful_pings", ping_info.get("successful_pings", 0))
                            .field("failed_pings", ping_info.get("failed_pings", 0))
                        )
                        batch.append(point)
                
                # DOCKER METRICS
                if "docker_metrics" in data:
                    docker_data = data["docker_metrics"]
                    container_count = docker_data.get("docker_container_count", None)
                    if container_count is not None:
                        point = (
                            Point("docker_metrics_summary")
                            .tag("site_id", site_id)
                            .field("docker_container_count", container_count)
                        )
                        batch.append(point)

                    containers = docker_data.get("containers", [])
                    for container in containers:
                        point = (
                            Point("docker_metrics")
                            .tag("site_id", site_id)
                            .tag("container_name", container.get("name", "unknown"))
                            .field("cpu_usage_percent", container.get("cpu_usage_percent", 0))
                            .field("ram_usage_bytes", container.get("ram_usage_bytes", 0))
                            .field("net_rx_bytes", container.get("net_rx_bytes", 0))
                            .field("net_tx_bytes", container.get("net_tx_bytes", 0))
                        )
                        batch.append(point)

                # Write batch to InfluxDB
                if batch:
                    write_api.write(bucket=influxdb_bucket, org=influxdb_org, record=batch)
                    log.info(
                        f"[INFLUX WRITE] site_id={site_id} | "
                        f"system_metrics={'system_metrics' in data} | "
                        f"ping_metrics={len(data.get('ping_metrics', {}))} targets | "
                        f"containers={len(data.get('docker_metrics', {}).get('containers', []))} | "
                        f"points={len(batch)}"
                    )
                    batch.clear()

            except json.JSONDecodeError as e:
                log.error(f"JSON parsing error: {e} - Raw Message: {msg.value()}")

    except KeyboardInterrupt:
        log.info("Stopping Kafka consumer due to KeyboardInterrupt...")
    finally:
        log.info("Closing Kafka consumer and InfluxDB connection.")
        consumer.close()
        influx_client.close()

if __name__ == "__main__":
    consume_messages()
