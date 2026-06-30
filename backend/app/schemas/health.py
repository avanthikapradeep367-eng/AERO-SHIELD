"""
schemas/health.py — Health check response schema.
"""

from pydantic import BaseModel, Field
from datetime import datetime


class HealthResponse(BaseModel):
    """Response schema for GET /api/v1/health."""

    status: str = Field(
        ..., description="Overall service health: 'operational' | 'degraded'"
    )
    version: str = Field(..., description="API version string")
    database: str = Field(
        ..., description="Database connectivity: 'connected' | 'unreachable'"
    )
    blockchain: str = Field(
        ..., description="Blockchain layer status (mocked until Member 2 integration)"
    )
    ai_engine: str = Field(
        ..., description="AI engine status (mocked until Member 3 integration)"
    )
    timestamp: datetime = Field(..., description="UTC timestamp of the health check")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "operational",
                    "version": "1.0.0",
                    "database": "connected",
                    "blockchain": "reachable",
                    "ai_engine": "operational",
                    "timestamp": "2026-06-29T10:00:00Z",
                }
            ]
        }
    }
