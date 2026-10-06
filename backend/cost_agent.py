"""
cost_agent.py — FacilityOps Cost Optimization Agent (Compatibility Entry Point)
Re-exports the modular Cost Optimization Agent implementation from backend.agents.cost.
"""

from agents.cost import (
    CostOptimizationAgent,
    get_cost_agent,
)

__all__ = [
    "CostOptimizationAgent",
    "get_cost_agent",
]
