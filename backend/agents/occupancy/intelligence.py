from datetime import datetime
from typing import Dict, List


def export_facility_intelligence_payload(facility_id: int, ov: Dict, insights: List[Dict]) -> Dict:
    """Standardized schema output for downstream cross-agent orchestration in Milestone 4."""
    status = "CRITICAL" if ov["overcrowded_count"] > 0 else ("WARNING" if ov["high_utilization_count"] > 0 else "NORMAL")
    severity = "HIGH" if ov["overcrowded_count"] > 0 else ("MEDIUM" if ov["high_utilization_count"] > 0 else "LOW")

    recommendations = [ins["action"] for ins in insights]

    return {
        "agent": "occupancy",
        "facility_id": facility_id,
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "severity": severity,
        "metrics": {
            "total_occupancy": ov["total_occupancy"],
            "total_capacity": ov["total_capacity"],
            "occupancy_rate": ov["occupancy_rate"],
            "overcrowded_zones": ov["overcrowded_count"],
            "underutilized_zones": ov["underutilized_count"],
        },
        "insights": [ins["detail"] for ins in insights],
        "recommendations": recommendations
    }
