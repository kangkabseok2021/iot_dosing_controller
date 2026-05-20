#!/usr/bin/env bash
# Usage: TARGET_HOST=192.168.1.10 ./scripts/deploy.sh
set -euo pipefail

TARGET_HOST="${TARGET_HOST:?Set TARGET_HOST to device IP/hostname}"
REMOTE_DIR="/opt/ev-battery-hil"

echo "==> Building ARM64 binary..."
cmake -B bms/build-arm64 -S bms \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE=cmake/toolchain-arm64.cmake \
  -DBUILD_TESTING=OFF
cmake --build bms/build-arm64 --target bms_daemon -j4

echo "==> Deploying to $TARGET_HOST..."
ssh "$TARGET_HOST" "sudo mkdir -p $REMOTE_DIR"
scp bms/build-arm64/bms_daemon "$TARGET_HOST:$REMOTE_DIR/"
ssh "$TARGET_HOST" "sudo systemctl restart bms-daemon"

echo "==> Waiting for health check (30s)..."
for i in $(seq 1 30); do
  if curl -sf "http://$TARGET_HOST:8080/api/status" > /dev/null 2>&1; then
    echo "✓ Deployment successful"
    exit 0
  fi
  sleep 1
done
echo "✗ Health check failed after 30s"
exit 1
