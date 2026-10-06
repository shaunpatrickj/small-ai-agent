from typing import List, Dict, Optional
from .overview import get_cost_overview
from .trends import get_cost_trends
from .opportunities import get_optimization_opportunities
from .utilization import analyze_resource_utilization
from .qa import answer_cost_query
from .intelligence import export_facility_intelligence_payload


class CostOptimizationAgent:
    """
    Autonomous Cost Optimization Agent responsible for:
    1. Operational expenditure (OpEx) analysis across Energy, Maintenance, Security, Admin
    2. Category trend analysis and budget variance monitoring
    3. Traceable cost-saving opportunities identification (never claiming potential as realized)
    4. Resource utilization and financial efficiency (cost per sq.ft., cost per occupant)
    5. Natural language financial diagnostics and ROI explanations
    6. Standardized payload export for the Facility Intelligence Engine
    """

    def __init__(self):
        pass

    # ── 1. Cost Overview & OpEx Breakdown ──────────────────────────────────
    def get_cost_overview(self, facility_id: int = 1) -> Dict:
        return get_cost_overview(facility_id)

    # ── 2. Cost Trends Over Time ───────────────────────────────────────────
    def get_cost_trends(self, facility_id: int = 1) -> List[Dict]:
        return get_cost_trends(facility_id)

    # ── 3. Traceable Savings Opportunities ──────────────────────────────────
    def get_optimization_opportunities(self, facility_id: int = 1, status: Optional[str] = None) -> List[Dict]:
        return get_optimization_opportunities(facility_id, status=status)

    # ── 4. Resource Utilization & Financial Insights ────────────────────────
    def analyze_resource_utilization(self, facility_id: int = 1) -> Dict:
        return analyze_resource_utilization(facility_id)

    # ── 5. Financial Q&A Natural Language Support ───────────────────────────
    def answer_cost_query(self, query: str, facility_id: int = 1) -> Dict:
        return answer_cost_query(query, facility_id)

    # ── 6. Facility Intelligence Standardized Payload Export ────────────────
    def export_facility_intelligence_payload(self, facility_id: int = 1) -> Dict:
        return export_facility_intelligence_payload(facility_id)


# Singleton accessor
_cost_agent_instance = None


def get_cost_agent() -> CostOptimizationAgent:
    global _cost_agent_instance
    if _cost_agent_instance is None:
        _cost_agent_instance = CostOptimizationAgent()
    return _cost_agent_instance
