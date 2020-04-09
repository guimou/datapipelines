#!/bin/bash
docker run shonpaz123/notify \
  -e ENDPOINT_URL \
  -a ACCESS_KEY \
  -s SECRET_KEY \
  -b BUCKET_NAME \
  -ke KAFKA_ENDPOINT \
  -t TOPIC \
  /