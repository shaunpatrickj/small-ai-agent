from datetime import datetime
from typing import Dict, Optional
from .overview import get_cost_overview
from .utilization import analyze_resource_utilization


def export_facility_intelligence_payload(facility_id: int = 1, ov: Optional[Dict] = None, util: Optional[Dict] = None) -> Dict:
    """
    Common Agent Output Contract for downstream cross-agent orchestration.
    """
    if ov is None:
        ov = get_cost_overview(facility_id)
    if util is None:
        util = analyze_resource_utilization(facility_id, ov=ov)

    status = "WARNING" if ov["net_budget_variance"] > 0 else "NORMAL"
    severity = "MEDIUM" if ov["net_budget_variance_pct"] > 5.0 else ("LOW" if ov["net_budget_variance"] <= 0 else "INFO")

    insights = [ins["finding"] for ins in util["insights"]]
    recommendations = [ins["action"] for ins in util["insights"]]

    return {
        "agent": "cost",
        "facility_id": facility_id,
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "severity": severity,
        "metrics": {
            "total_operating_cost": ov["total_operating_cost"],
            "total_budget_allocated": ov["total_budget_allocated"],
            "net_budget_variance": ov["net_budget_variance"],
            "net_budget_variance_pct": ov["net_budget_variance_pct"],
            "cost_per_sqft": ov["cost_per_sqft"],
            "cost_per_occupant": ov["cost_per_occupant"],
            "potential_savings": ov["opportunities_summary"]["potential_savings"],
            "opportunity_count": ov["opportunities_summary"]["total_opportunities"]
        },
        "insights": insights,
        "recommendations": recommendations,
        "confidence": 0.94
    }
