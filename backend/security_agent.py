"""
security_agent.py — FacilityOps Security Agent (Compatibility Entry Point)
Re-exports the modular Security Agent implementation from backend.agents.security.
"""

from agents.security import (
    SEVERITY_WEIGHTS,
    EVENT_BASE_RISKS,
    SecurityAgent,
    get_security_agent,
)

__all__ = [
    "SEVERITY_WEIGHTS",
    "EVENT_BASE_RISKS",
    "SecurityAgent",
    "get_security_agent",
]
