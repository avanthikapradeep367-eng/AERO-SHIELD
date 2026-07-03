#!/usr/bin/env bash
# AERO-SHIELD X — Health Check Script
# Used by Docker HEALTHCHECK and CI pipelines.
# Exits 0 if API is healthy, 1 otherwise.

set -euo pipefail

HOST="${AEROSHIELD_HOST:-localhost}"
PORT="${AEROSHIELD_PORT:-8000}"
BASE="http://${HOST}:${PORT}"

echo "=== AERO-SHIELD Health Check ==="
echo "Target: ${BASE}"

# Liveness probe (fast)
LIVE=$(curl -sf "${BASE}/system/health/live" 2>/dev/null || echo "FAIL")
if echo "$LIVE" | grep -q '"alive"'; then
    echo "[OK] Liveness: alive"
else
    echo "[FAIL] Liveness check failed"
    exit 1
fi

# Full health report
HEALTH=$(curl -sf "${BASE}/system/health" 2>/dev/null || echo "{}")
STATUS=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('overall_status','UNKNOWN'))" 2>/dev/null || echo "UNKNOWN")

echo "[INFO] Overall system status: ${STATUS}"

if [[ "$STATUS" == "HEALTHY" ]]; then
    echo "[OK] All systems operational"
    exit 0
elif [[ "$STATUS" == "DEGRADED" ]]; then
    echo "[WARN] System degraded — check /system/health for details"
    exit 0
else
    echo "[FAIL] System status: ${STATUS}"
    exit 1
fi
