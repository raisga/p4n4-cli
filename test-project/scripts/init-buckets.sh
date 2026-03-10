#!/usr/bin/env bash
# ==============================================================================
# InfluxDB Bucket Initialization
# ==============================================================================
# Creates all architecture-defined buckets for the p4n4 IoT stack.
# Runs after InfluxDB initial setup via docker-entrypoint-initdb.d.
#
# Buckets created:
#   raw_telemetry    - all inbound sensor readings           (30d retention)
#   processed_metrics - downsampled / aggregated data        (365d retention)
#   ai_events        - AI annotations, anomaly flags         (infinite)
#   system_health    - Node-RED and stack component metrics  (7d retention)
#   sandbox          - development / testing                 (configurable)
#
# Note: raw_telemetry is the DOCKER_INFLUXDB_INIT_BUCKET and is created
# automatically by InfluxDB on first run. This script creates the rest.
# ==============================================================================

set -e

ORG="${DOCKER_INFLUXDB_INIT_ORG:-ming}"
TOKEN="${DOCKER_INFLUXDB_INIT_ADMIN_TOKEN:-p4n4-stack-token}"
HOST="http://localhost:8086"
MAX_ATTEMPTS=30

SANDBOX_BUCKET="${INFLUXDB_SANDBOX_BUCKET:-sandbox}"
SANDBOX_RETENTION="${INFLUXDB_SANDBOX_RETENTION:-30d}"
BUCKET_PROCESSED="${INFLUXDB_BUCKET_PROCESSED:-processed_metrics}"
BUCKET_AI_EVENTS="${INFLUXDB_BUCKET_AI_EVENTS:-ai_events}"
BUCKET_HEALTH="${INFLUXDB_BUCKET_HEALTH:-system_health}"

# ------------------------------------------------------------------------------
# Wait for InfluxDB API
# ------------------------------------------------------------------------------
echo "[init-buckets] Waiting for InfluxDB API..."
attempt=0
while [ "$attempt" -lt "$MAX_ATTEMPTS" ]; do
    if influx ping --host "$HOST" 2>/dev/null; then
        echo "[init-buckets] InfluxDB API ready."
        break
    fi
    echo "[init-buckets]   Attempt $((attempt + 1))/$MAX_ATTEMPTS..."
    sleep 2
    attempt=$((attempt + 1))
done

if [ "$attempt" -eq "$MAX_ATTEMPTS" ]; then
    echo "[init-buckets] ERROR: InfluxDB API not ready after $((MAX_ATTEMPTS * 2))s. Buckets NOT created."
    exit 1
fi

# ------------------------------------------------------------------------------
# Helper: create bucket if it does not already exist
# ------------------------------------------------------------------------------
create_bucket() {
    local name="$1"
    local retention="$2"   # e.g. "30d", "365d", "7d", or "0" for infinite

    if influx bucket list --host "$HOST" --token "$TOKEN" --org "$ORG" 2>/dev/null \
        | grep -q "^$name\b"; then
        echo "[init-buckets] Bucket '$name' already exists — skipping."
        return 0
    fi

    local args=(
        --name "$name"
        --org "$ORG"
        --token "$TOKEN"
        --host "$HOST"
    )
    [ -n "$retention" ] && args+=(--retention "$retention")

    if influx bucket create "${args[@]}"; then
        echo "[init-buckets] Bucket '$name' created (retention: ${retention:-infinite})."
    else
        echo "[init-buckets] ERROR: Failed to create bucket '$name'."
        exit 1
    fi
}

# ------------------------------------------------------------------------------
# Create buckets
# ------------------------------------------------------------------------------
echo "[init-buckets] Creating p4n4 IoT buckets..."

create_bucket "$BUCKET_PROCESSED"  "365d"
create_bucket "$BUCKET_AI_EVENTS"  "0"
create_bucket "$BUCKET_HEALTH"     "7d"
create_bucket "$SANDBOX_BUCKET"    "$SANDBOX_RETENTION"

echo "[init-buckets] All buckets initialized."
