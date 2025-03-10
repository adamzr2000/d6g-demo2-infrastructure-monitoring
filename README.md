# Kafka-Docker-MM2

This repository provides an example of synchronizing a distributed Kafka environment using MirrorMaker 2 (MM2). The deployment leverages MM2 to replicate data between Kafka clusters. MM2 runs as a standard Kafka broker with a modified entrypoint configured via `mm2.properties`.

This setup uses Kafka with RAFT and includes Kafka-UI for monitoring. It is based on Bitnami Kafka instead of Confluent Kafka and follows the approach outlined in [this guide](https://medium.com/larus-team/how-to-setup-mirrormaker-2-0-on-apache-kafka-multi-cluster-environment-87712d7997a4) with modifications.

## Project Structure
- `edge/` - Scripts for managing the Kafka instance at the edge (D6G site).
- `producer-consumer/` - Example Python-based Kafka producers and consumers.

## Quick Start

### Start the Edge Kafka Instance
```bash
cd edge
./start_edge.sh --local-ip 10.5.1.21
```

### Start Infrastructure Monitoring
```bash
./start_infrastructure_monitoring.sh
```
- Kafka UI: [http://10.5.1.21:8080](http://10.5.1.21:8080/)
- Grafana Dashboard: [http://10.5.1.21:3000](http://10.5.1.21:3000/)

![grafana](./grafana-dashboard.png)


### Stop Infrastructure Monitoring
```bash
./stop_infrastructure_monitoring.sh
```

### Stop the Edge Kafka Instance
```bash
cd edge
./stop_edge.sh
```

## Utility Commands

### Edge Site Control
- Start Kafka Edge:
  ```bash
  ./start_edge.sh --local-ip 10.5.1.21
  ```
- Stop Kafka Edge:
  ```bash
  ./stop_edge.sh
  ```

### Producer Commands
- Start a Kafka Producer:
  ```bash
  python3 kafka_producer.py --file config/configP1.conf
  ```

### Consumer Commands
- Start a Kafka Consumer:
  ```bash
  python3 kafka_consumer.py --file configC1.conf
  ```

### InfluxDB Integration
- Send Kafka Data to InfluxDB:
  ```bash
  python3 kafka_to_influx.py --file configCInfluxDB.conf
  ```

