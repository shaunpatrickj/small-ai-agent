"""
FacilityOps — Cost Optimization Agent Package
Submodules:
- overview: 30-day OpEx accounting, category breakdown, budget variance
- trends: Daily expense time-series partitioned by cost category
- opportunities: Quantified and traceable cost-saving opportunities
- utilization: Financial efficiency and operational intensity analytics
- qa: Natural language financial diagnostics and ROI answers
- intelligence: Standardized facility intelligence payload export
- agent: CostOptimizationAgent orchestrator and singleton accessor
"""

from .overview import get_cost_overview
from .trends import get_cost_trends
from .opportunities import get_optimization_opportunities
from .utilization import analyze_resource_utilization
from .qa import answer_cost_query
from .intelligence import export_facility_intelligence_payload
from .agent import CostOptimizationAgent, get_cost_agent

__all__ = [
    "get_cost_overview",
    "get_cost_trends",
    "get_optimization_opportunities",
    "analyze_resource_utilization",
    "answer_cost_query",
    "export_facility_intelligence_payload",
    "CostOptimizationAgent",
    "get_cost_agent",
]
