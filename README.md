# Kafka-docker-mm2
This is an example of synchronization/exporting of distriuted Kafka environemnt exploiting MirrorMaker2.

The deployment uses MirrorMaker2 to syncronize information from one cluster to another one. The MM2 istance is a same Kafka broker image but with a different entrypoint. The relative configuration file is _mm2.properties_.
This example is based on the following guide, [Medium article](https://medium.com/larus-team/how-to-setup-mirrormaker-2-0-on-apache-kafka-multi-cluster-environment-87712d7997a4) but with a different base image of Kafka (bitami vs confluent).

This version is based on the new standalone Kafka with RAFT, plus Kafka-UI.

# Code structure
3 folders are provided:
- cloud: files for the control of the cloud DC kafka instance
- edge: files for the control of an edge D6G kafka instance
- producer-consumer: example of consumer and producers based on python

# Cloud DC commands
Run:

```bash
./start_cloud.sh --local-ip <ip-addr>
```

Stop:
```bash
./stop_cloud.sh
```

# Edge site commands
Run:
```bash
./start_edge.sh --local-ip <ip-addr>
```
Kafka UI at [http://127.0.0.1:8080/](http://127.0.0.1:8080/)

Stop:
```bash
./stop_edge.sh
```

# Producer commands
Run:
```bash
python3 kafka_producer.py --file config/configP1.conf
```

# Consumer commands
Run:
```bash
python3 kafka_consumer.py --file config/configC1.conf
```

or

```bash
./run_kafka_agent.sh --script kafka_consumer.py --file-name configC1.conf
```

# InfluxDB - Grafana integration
Run:
```bash
./run_kafka_agent.sh --script kafka_to_influx.py --file-name configCInfluxDB.conf
```

Kafka UI at [http://127.0.0.1:3000/](http://127.0.0.1:3000/)