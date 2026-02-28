#!/bin/bash
echo "Starting Cloud SQL Proxy..."
#!/bin/bash

# Cloud SQL Proxy Script
INSTANCE_CONNECTION_NAME="crysoft:us-central1:overwatch"
CREDENTIALS_FILE="./configs/crysoft-f9695743736c.json"

cloud-sql-proxy $INSTANCE_CONNECTION_NAME \
  --credentials-file=$CREDENTIALS_FILE \
  --address=127.0.0.1 \
  --port=5432