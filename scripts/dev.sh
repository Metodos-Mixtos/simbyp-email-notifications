#!/bin/bash
set -e

SOCKET_DIR="/tmp/cloudsql"
INSTANCE="bosques-bogota-416214:us-central1:simbyp-users-db"

echo "🔌 Starting Cloud SQL Proxy in background..."
mkdir -p "$SOCKET_DIR"
cloud-sql-proxy --unix-socket "$SOCKET_DIR" "$INSTANCE" &
PROXY_PID=$!

echo "✅ Proxy running (PID: $PROXY_PID)"
echo "🚀 Starting app..."
echo ""

trap "echo '🛑 Shutting down...'; kill $PROXY_PID 2>/dev/null || true" EXIT

python main.py
