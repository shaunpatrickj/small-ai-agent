from typing import Dict, List, Any


def answer_occupancy_query(query: str, facility_id: int, ov: Dict, insights: List[Dict], forecaster: Any) -> Dict:
    """Answer natural language inquiries regarding occupancy and space utilization."""
    q = query.lower()

    if "overcrowd" in q or "capacity" in q or "congest" in q:
        over = [z for z in ov["zones"] if z["overcrowding"]]
        if over:
            answer = f"Overcrowding detected in {len(over)} zones: " + ", ".join(f"{z['zone']} ({z['occupancy_count']}/{z['capacity']}, {round(z['occupancy_rate']*100)}%)" for z in over) + ". Divert personnel to underutilized zones."
        else:
            highest_zone = ov["zones"][0]["zone"] if ov["zones"] else "N/A"
            highest_rate = round(ov["zones"][0]["occupancy_rate"] * 100) if ov["zones"] else 0
            answer = f"No overcrowding currently detected across {ov['total_zones']} zones. Highest utilization is {highest_zone} at {highest_rate}%."
    elif "underutil" in q or "empty" in q or "idle" in q:
        under = [z for z in ov["zones"] if z["underutilized"]]
        if under:
            answer = f"Found {len(under)} underutilized zones: " + ", ".join(f"{z['zone']} ({z['occupancy_count']}/{z['capacity']})" for z in under) + ". Consider adjusting HVAC setpoints to save energy."
        else:
            answer = "All zones are maintaining healthy operational usage above 25%."
    elif "forecast" in q or "predict" in q or "tomorrow" in q:
        fc = forecaster.forecast_24h(facility_id)
        peak = max(fc, key=lambda x: x["predicted_occupancy"])
        answer = f"Occupancy demand is forecast to peak at {peak['hour']} with ~{peak['predicted_occupancy']} occupants ({peak['predicted_pct']}% load). Off-peak valley expected overnight."
    elif "zone" in q or "room" in q:
        answer = f"Currently monitoring {ov['total_zones']} zones with total head count of {ov['total_occupancy']}/{ov['total_capacity']} occupants ({ov['occupancy_pct']}% capacity)."
    else:
        answer = f"Facility occupancy is currently at {ov['occupancy_pct']}% ({ov['total_occupancy']}/{ov['total_capacity']} occupants across {ov['total_zones']} zones). Overcrowded zones: {ov['overcrowded_count']}, Underutilized zones: {ov['underutilized_count']}."

    return {
        "facility_id": facility_id,
        "query": query,
        "answer": answer,
        "summary": ov,
        "insights": insights
    }
