"""
maintenance_agent.py — FacilityOps Maintenance Agent (Compatibility Entry Point)
Re-exports the modular Maintenance Agent implementation from backend.agents.maintenance.
"""

from agents.maintenance import (
    ASSET_THRESHOLDS,
    MaintenanceAgent,
    get_maintenance_agent,
)

__all__ = [
    "ASSET_THRESHOLDS",
    "MaintenanceAgent",
    "get_maintenance_agent",
]
