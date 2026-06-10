#!/bin/bash
set -e

SOCKET_DIR="/tmp/cloudsql"
INSTANCE="bosques-bogota-416214:us-central1:simbyp-users-db"

echo "🔌 Starting Cloud SQL Proxy..."
mkdir -p "$SOCKET_DIR"
echo "Socket path: $SOCKET_DIR/$INSTANCE"
echo "Keep this terminal open while developing."
echo ""

cloud-sql-proxy --unix-socket "$SOCKET_DIR" "$INSTANCE"
