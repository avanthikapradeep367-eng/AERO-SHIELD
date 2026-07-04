"""
AERO-SHIELD X — System Health Monitor

Checks all system components and returns structured health status suitable
for the React dashboard health panel and Kubernetes/Docker liveness probes.

Component checks:
    blockchain  — Ganache / EVM node reachability
    contract    — Smart contract deployment and call availability
    wallet      — ETH balance and wallet accessibility
    ai_engine   — SentinelX (Member 3) in-process model status — SentinelX runs
                  inside this FastAPI process (see app/services/ai_service.py),
                  not as a standalone service, so this reports whether a trained
                  model is loaded rather than probing any network port.
    fastapi     — Self (always ONLINE when this runs)
    memory      — Host RAM usage via psutil
    cpu         — Host CPU usage via psutil
    disk        — Host disk usage via psutil

All checks are wrapped with a 3-second timeout via threading.
Status values: ONLINE | DEGRADED | OFFLINE | UNKNOWN
"""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from typing import Any

import psutil

from app.core.logger import get_logger

logger = get_logger("dashboard.health")


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _run_with_timeout(fn, timeout: float = 3.0, default=None):
    result_holder: list[Any] = [default]
    exc_holder:    list[Exception | None] = [None]

    def target():
        try:
            result_holder[0] = fn()
        except Exception as e:
            exc_holder[0] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if exc_holder[0]:
        raise exc_holder[0]
    return result_holder[0]


def _component(name: str, status: str, detail: str | None = None, extra: dict | None = None) -> dict[str, Any]:
    d: dict[str, Any] = {
        "component": name,
        "status":    status,
        "checked_at": _now_iso(),
    }
    if detail:
        d["detail"] = detail
    if extra:
        d.update(extra)
    return d


# ── Individual Checks ────────────────────────────────────────────────────────────────

def _check_blockchain() -> dict[str, Any]:
    try:
        from app.blockchain.blockchain_service import BlockchainService
        info = _run_with_timeout(BlockchainService().verify_connection, timeout=3.0, default={})
        if info.get("connected"):
            return _component("blockchain", "ONLINE", "Node reachable", {
                "block_number":    info.get("block_number"),
                "chain_id":        info.get("chain_id"),
                "rpc_url":         info.get("rpc_url"),
                "network":         info.get("network", "Unknown"),
            })
        return _component("blockchain", "OFFLINE", "RPC node not connected")
    except Exception as exc:
        return _component("blockchain", "OFFLINE", str(exc))


def _check_contract() -> dict[str, Any]:
    try:
        from app.blockchain.blockchain_service import BlockchainService
        bc = BlockchainService()
        if not bc.contract:
            return _component("contract", "OFFLINE", "Contract not loaded")
        addr = bc.contract.address
        return _component("contract", "ONLINE", f"Deployed at {addr}", {"contract_address": addr})
    except Exception as exc:
        return _component("contract", "OFFLINE", str(exc))


def _check_wallet() -> dict[str, Any]:
    try:
        from app.blockchain.web3_client import get_web3, get_account
        from app.blockchain.config import load_config
        cfg = load_config()
        w3  = get_web3()
        acct = get_account()
        wallet_addr = acct.address
        bal_wei = _run_with_timeout(lambda: w3.eth.get_balance(wallet_addr), timeout=3.0, default=None)
        if bal_wei is None:
            return _component("wallet", "DEGRADED", "Could not read balance")
        bal_eth = float(w3.from_wei(bal_wei, "ether"))
        status = "ONLINE" if bal_eth > 0.01 else "DEGRADED"
        return _component("wallet", status, f"{bal_eth:.6f} ETH", {
            "address":     wallet_addr,
            "balance_eth": round(bal_eth, 6),
            "balance_wei": bal_wei,
        })
    except Exception as exc:
        return _component("wallet", "UNKNOWN", str(exc))


def _check_ai_engine() -> dict[str, Any]:
    """
    SentinelX (Member 3) is integrated in-process (app/services/ai_service.py
    -> app.ai.sentinelx.SentinelXEngine) — it is not a standalone service, so
    there is no port to probe. Status reflects whether a trained model is
    loaded, mirroring the same AIService.get_status() used by /api/v1/health.
    """
    try:
        from app.services.ai_service import AIService

        info = _run_with_timeout(lambda: asyncio.run(AIService().get_status()), timeout=5.0, default=None)
        if info is None:
            return _component("ai_engine", "UNKNOWN", "AI engine status check timed out")

        if info.get("status") == "operational":
            return _component("ai_engine", "ONLINE", f"Model loaded: {info.get('model')}", {
                "model": info.get("model"),
                "cuda_available": info.get("cuda_available"),
                "device": info.get("device"),
            })

        return _component(
            "ai_engine",
            "DEGRADED",
            "SentinelX engine is running but no trained model is loaded "
            "(AI_MODEL_WEIGHTS_PATH not set or failed to load)",
            {
                "cuda_available": info.get("cuda_available"),
                "device": info.get("device"),
            },
        )
    except Exception as exc:
        return _component("ai_engine", "OFFLINE", f"SentinelX engine failed to initialize: {exc}")


def _check_fastapi() -> dict[str, Any]:
    return _component("fastapi", "ONLINE", "Backend API process running")


def _check_memory() -> dict[str, Any]:
    try:
        m = psutil.virtual_memory()
        pct = m.percent
        status = "ONLINE" if pct < 85 else "DEGRADED" if pct < 95 else "OFFLINE"
        return _component("memory", status, f"{pct:.1f}% used", {
            "total_gb":     round(m.total / (1024 ** 3), 2),
            "available_gb": round(m.available / (1024 ** 3), 2),
            "used_percent": pct,
        })
    except Exception as exc:
        return _component("memory", "UNKNOWN", str(exc))


def _check_cpu() -> dict[str, Any]:
    try:
        pct = psutil.cpu_percent(interval=0.2)
        status = "ONLINE" if pct < 80 else "DEGRADED" if pct < 95 else "OFFLINE"
        return _component("cpu", status, f"{pct:.1f}% load", {
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": pct,
        })
    except Exception as exc:
        return _component("cpu", "UNKNOWN", str(exc))


def _check_disk() -> dict[str, Any]:
    try:
        d = psutil.disk_usage("/")
        pct = d.percent
        status = "ONLINE" if pct < 85 else "DEGRADED" if pct < 95 else "OFFLINE"
        return _component("disk", status, f"{pct:.1f}% used", {
            "total_gb":  round(d.total / (1024 ** 3), 2),
            "free_gb":   round(d.free  / (1024 ** 3), 2),
            "used_percent": pct,
        })
    except Exception as exc:
        # On Windows "/" may fail — try C:
        try:
            d = psutil.disk_usage("C:\\")
            pct = d.percent
            status = "ONLINE" if pct < 85 else "DEGRADED"
            return _component("disk", status, f"C:\\ {pct:.1f}% used", {
                "total_gb":  round(d.total / (1024 ** 3), 2),
                "free_gb":   round(d.free  / (1024 ** 3), 2),
                "used_percent": pct,
            })
        except Exception as exc2:
            return _component("disk", "UNKNOWN", str(exc2))


# ── Public: Full Health Check ────────────────────────────────────────────────────────

_CHECKERS = [
    _check_fastapi,
    _check_blockchain,
    _check_contract,
    _check_wallet,
    _check_ai_engine,
    _check_memory,
    _check_cpu,
    _check_disk,
]

# Simple 10-second TTL cache for health
_health_cache: dict[str, Any] | None = None
_health_expiry: float = 0.0
_health_lock = threading.RLock()


def check_all() -> dict[str, Any]:
    """
    Run all component health checks concurrently and return an aggregated report.

    Returns:
        {
            "overall_status": "HEALTHY" | "DEGRADED" | "CRITICAL",
            "checked_at": ISO-8601,
            "components": [...],
            "summary": {"online": N, "degraded": N, "offline": N, "unknown": N},
            "elapsed_ms": float,
        }
    """
    global _health_cache, _health_expiry
    with _health_lock:
        if _health_cache and time.monotonic() < _health_expiry:
            return _health_cache

    t0 = time.monotonic()
    results: list[dict[str, Any]] = [{}] * len(_CHECKERS)

    def run(i: int, fn):
        try:
            results[i] = fn()
        except Exception as exc:
            results[i] = _component(fn.__name__.replace("_check_", ""), "UNKNOWN", str(exc))

    threads = [threading.Thread(target=run, args=(i, fn), daemon=True) for i, fn in enumerate(_CHECKERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    components = [r for r in results if r]
    summary = {"online": 0, "degraded": 0, "offline": 0, "unknown": 0}
    for c in components:
        s = c.get("status", "UNKNOWN").upper()
        if s == "ONLINE":
            summary["online"] += 1
        elif s == "DEGRADED":
            summary["degraded"] += 1
        elif s == "OFFLINE":
            summary["offline"] += 1
        else:
            summary["unknown"] += 1

    if summary["offline"] >= 2:
        overall = "CRITICAL"
    elif summary["offline"] >= 1 or summary["degraded"] >= 2:
        overall = "DEGRADED"
    elif summary["degraded"] >= 1 or summary["unknown"] >= 2:
        overall = "DEGRADED"
    else:
        overall = "HEALTHY"

    report = {
        "overall_status": overall,
        "checked_at":     _now_iso(),
        "components":     components,
        "summary":        summary,
        "elapsed_ms":     round((time.monotonic() - t0) * 1000, 2),
    }

    with _health_lock:
        _health_cache = report
        _health_expiry = time.monotonic() + 10.0

    return report
