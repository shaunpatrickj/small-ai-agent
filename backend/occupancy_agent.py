"""
occupancy_agent.py — FacilityOps Occupancy Agent (Compatibility Entry Point)
Re-exports the modular Occupancy Agent implementation from backend.agents.occupancy.
"""

from agents.occupancy import (
    OccupancyAgent,
    get_occupancy_agent,
)

__all__ = [
    "OccupancyAgent",
    "get_occupancy_agent",
]
