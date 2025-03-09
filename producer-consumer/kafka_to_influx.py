import json
import logging
import argparse
from configparser import ConfigParser
from confluent_kafka import Consumer, KafkaException
from influxdb_client import InfluxDBClient, WriteOptions, Point

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

BATCH_SIZE = 1

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
    write_api = influx_client.write_api(write_options=WriteOptions(batch_size=10, flush_interval=5000))
    log.info(f"Successfully connected to InfluxDB at {influxdb_url}")
except Exception as e:
    log.error(f"Error connecting to InfluxDB: {e}")
    exit(1)

# Function to Consume Kafka Messages and Write to InfluxDB
def consume_messages():
    batch = []
    try:
        log.info("Starting Kafka message consumption...")
        while True:
            msg = consumer.poll(1.0)

            if msg is None:
                continue
            if msg.error():
                log.warning(f"Kafka message error: {msg.error()}")
                continue

            try:
                # Parse JSON message
                data = json.loads(msg.value().decode("utf-8"))
                site_id = data.get("site_id", "unknown")

                # ✅ Process System Metrics
                if "system_metrics" in data:
                    system_metrics = data["system_metrics"]
                    point = (
                        Point("system_metrics")
                        .tag("site_id", site_id)
                        .field("cpu_usage_percent", system_metrics.get("cpu_usage_percent", 0))
                        .field("ram_usage_percent", system_metrics.get("ram_usage_percent", 0))
                        .field("total_ram_gb", system_metrics.get("total_ram_gb", 0))
                        .field("free_ram_gb", system_metrics.get("free_ram_gb", 0))
                    )
                    batch.append(point)

                # ✅ Process Network Metrics
                if "network_metrics" in data:
                    for target_name, network in data["network_metrics"].items():
                        point = (
                            Point("network_metrics")
                            .tag("site_id", site_id)
                            .tag("target_name", target_name)
                            .tag("target_ip", network.get("ip", "unknown"))
                            .field("latency_ms", network.get("latency_ms", 0))
                            .field("packet_loss_percent", network.get("packet_loss_percent", 0))
                            .field("total_pings", network.get("total_pings", 0))
                            .field("successful_pings", network.get("successful_pings", 0))
                            .field("failed_pings", network.get("failed_pings", 0))
                        )
                        batch.append(point)

                # ✅ Batch write to InfluxDB
                if batch:
                    write_api.write(bucket=influxdb_bucket, org=influxdb_org, record=batch)
                    log.info(f"✅ Successfully wrote {len(batch)} records to InfluxDB.")
                    batch.clear()

            except json.JSONDecodeError as e:
                log.error(f"JSON parsing error: {e} - Raw Message: {msg.value()}")

    except KeyboardInterrupt:
        log.info("🔴 Stopping Kafka consumer due to KeyboardInterrupt...")
    finally:
        log.info("Closing Kafka consumer and InfluxDB connection.")
        consumer.close()
        influx_client.close()

if __name__ == "__main__":
    consume_messages()
