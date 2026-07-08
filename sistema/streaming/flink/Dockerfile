# ============================================================================
# Imagem Flink com PyFlink + conectores (Kafka, Avro) para os jobs de analise
# continua. Base apache/flink 1.18.1; adiciona Python 3.10, apache-flink e os
# JARs sql-connector-kafka + avro em /opt/flink/lib.
# ============================================================================
FROM apache/flink:1.18.1-scala_2.12-java11

ENV PYTHON_VERSION=3.10

# Python + pip (necessarios para PyFlink)
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends python3 python3-pip python3-dev; \
    ln -sf /usr/bin/python3 /usr/bin/python; \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir apache-flink==1.18.1 fastavro==1.9.4

# Conectores Flink SQL (Kafka + Avro) e formato avro
ARG FLINK_V=1.18.1
ARG KAFKA_CONN=3.1.0-1.18
RUN set -eux; cd /opt/flink/lib; \
    curl -fsSL -o flink-sql-connector-kafka-${KAFKA_CONN}.jar \
      https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/${KAFKA_CONN}/flink-sql-connector-kafka-${KAFKA_CONN}.jar; \
    curl -fsSL -o flink-sql-avro-${FLINK_V}.jar \
      https://repo1.maven.org/maven2/org/apache/flink/flink-sql-avro/${FLINK_V}/flink-sql-avro-${FLINK_V}.jar

# fleetlib e os jobs sao montados em /opt/flink/{fleetlib,jobs} pelo compose.
ENV PYTHONPATH=/opt/flink
