"""
api/blockchain/health.py — Blockchain node health check endpoint.

GET /blockchain/health returns a comprehensive snapshot of the blockchain layer:
  • Ganache connection status
  • Current block number
  • Chain ID
  • Wallet address and ETH balance
  • Deployed contract address
  • Current gas price (Gwei)
  • Network label

This endpoint is designed to be polled by monitoring systems and the React
dashboard without triggering any on-chain state changes.  It is safe to call
frequently — all operations are view-only reads against the local node.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.blockchain.blockchain_service import BlockchainService
from app.blockchain.exceptions import BlockchainBaseError
from app.blockchain.utils import now_iso
from app.core.logger import get_logger
from .dependencies import get_blockchain_service, blockchain_error_json

logger = get_logger("api.blockchain.health")

router = APIRouter(tags=["Blockchain — Health"])

# Maps chain ID to a human-readable network label
_NETWORK_LABELS: dict[int, str] = {
    1:     "Ethereum Mainnet",
    5:     "Goerli Testnet",
    11155111: "Sepolia Testnet",
    137:   "Polygon Mainnet",
    1337:  "Ganache Local Network",
    31337: "Hardhat Local Network",
}


@router.get(
    "/health",
    summary="Blockchain node health check",
    description=(
        "Returns a full diagnostic snapshot of the blockchain integration layer. "
        "Checks the Ganache node connection, reads the current block, inspects the "
        "wallet balance and contract address, and reports the current gas price. "
        "All operations are read-only — no gas is consumed. "
        "Returns HTTP 200 even when partially degraded so callers can inspect the "
        "'connected' field to distinguish healthy from degraded states."
    ),
    responses={
        200: {"description": "Health snapshot returned (check 'connected' field for node status)"},
        503: {"description": "Cannot reach blockchain node at all"},
    },
)
def get_blockchain_health(
    request: Request,
    service: BlockchainService = Depends(get_blockchain_service),
) -> JSONResponse:
    """
    Blockchain layer health check.

    **curl example:**
    ```bash
    curl http://localhost:8000/blockchain/health
    ```

    **HTTPie example:**
    ```bash
    http GET http://localhost:8000/blockchain/health
    ```

    **Python requests example:**
    ```python
    import requests
    resp = requests.get("http://localhost:8000/blockchain/health")
    health = resp.json()
    print(health["data"]["connected"])   # True / False
    print(health["data"]["currentBlock"])
    ```
    """
    logger.info(
        "GET /blockchain/health | ip=%s",
        request.client.host if request.client else "unknown",
    )
    try:
        # Core connection diagnostics from BlockchainService
        status = service.verify_connection()

        chain_id: int | None = status.get("chain_id")
        network_label = _NETWORK_LABELS.get(chain_id, f"Unknown Network (Chain ID {chain_id})")

        # Gas price (in Wei — also expose Gwei for readability)
        gas_price_wei: int | None = None
        gas_price_gwei: str | None = None
        if status.get("connected"):
            try:
                gas_price_wei = service.w3.eth.gas_price
                gas_price_gwei = f"{gas_price_wei / 1e9:.4f} Gwei"
            except Exception as gas_exc:
                logger.warning("Could not fetch gas price: %s", gas_exc)

        health_data = {
            # Connection
            "connected":       status.get("connected", False),
            "nodeStatus":      "operational" if status.get("connected") else "unreachable",
            "rpcUrl":          status.get("rpc_url"),
            # Chain
            "chainId":         chain_id,
            "network":         network_label,
            "currentBlock":    status.get("block_number"),
            # Wallet
            "walletAddress":   status.get("wallet_address"),
            "walletBalance":   status.get("wallet_balance"),
            # Contract
            "contractAddress": status.get("contract_address"),
            # Gas
            "gasPrice":        str(gas_price_wei) if gas_price_wei is not None else None,
            "gasPriceGwei":    gas_price_gwei,
            # Meta
            "timestamp":       status.get("timestamp", now_iso()),
        }

        is_connected: bool = bool(status.get("connected"))
        message = (
            "Blockchain node is operational and contract is loaded."
            if is_connected
            else "Blockchain node is unreachable."
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": is_connected,
                "message": message,
                "timestamp": now_iso(),
                "transactionHash": None,
                "gasUsed": None,
                "data": health_data,
            },
        )

    except BlockchainBaseError as exc:
        # Node is so broken we can't even run verify_connection()
        logger.error("Health check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "message": str(exc),
                "errorCode": type(exc).__name__,
                "details": exc.details if exc.details else None,
            },
        )
    except Exception as exc:
        logger.exception("Unexpected error in blockchain health check")
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "message": f"Unexpected error: {exc}",
                "errorCode": type(exc).__name__,
                "details": None,
            },
        )
