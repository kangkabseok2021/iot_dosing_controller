#!/usr/bin/env bash
# Usage: TARGET_HOST=192.168.1.10 ./scripts/run-smoke-test.sh
set -euo pipefail

TARGET_HOST="${TARGET_HOST:?Set TARGET_HOST}"
API="http://$TARGET_HOST:8080"

echo "==> Smoke test: 60s CONSTANT_DISCHARGE"

INITIAL_SOC=$(curl -sf "$API/api/status" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['SoC'])")
echo "   Initial SoC: $INITIAL_SOC"

curl -sf -X POST "$API/api/sequences/CONSTANT_DISCHARGE/start" > /dev/null
echo "   Sequence started. Waiting 65s..."
sleep 65

FINAL_SOC=$(curl -sf "$API/api/status" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['SoC'])")
echo "   Final SoC:   $FINAL_SOC"

PASS=$(python3 -c "print('PASS' if $INITIAL_SOC - $FINAL_SOC >= 0.005 else 'FAIL')")
echo "   SoC delta: $(python3 -c "print($INITIAL_SOC - $FINAL_SOC)") — $PASS"
[ "$PASS" = "PASS" ] || exit 1
