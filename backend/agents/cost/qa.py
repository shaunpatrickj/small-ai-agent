from typing import Dict, Optional
from .overview import get_cost_overview


def answer_cost_query(query: str, facility_id: int = 1, ov: Optional[Dict] = None) -> Dict:
    """
    Answer natural language questions regarding facility financials, OpEx, and ROI.
    """
    if ov is None:
        ov = get_cost_overview(facility_id)
    q = query.lower()

    if "energy" in q:
        e = ov["cost_by_category"].get("ENERGY", {})
        ans = f"Energy operating expenditure for {ov['facility_name']} is ₹{e.get('amount', 0):,.2f} over the last 30 days (Budget: ₹{e.get('budget', 0):,.2f}, Variance: {e.get('variance_pct')}%)."
    elif "maintenance" in q:
        m = ov["cost_by_category"].get("MAINTENANCE", {})
        ans = f"Maintenance operating cost is ₹{m.get('amount', 0):,.2f} against a budget of ₹{m.get('budget', 0):,.2f}."
    elif "saving" in q or "opportunity" in q or "roi" in q:
        opp = ov["opportunities_summary"]
        ans = f"We have identified {opp['total_opportunities']} traceable cost-saving opportunities totaling ₹{opp['potential_savings']:,.2f} in potential savings (~{opp['potential_saving_pct']}% of baseline). Note: these are estimated potential savings based on operational models."
    elif "budget" in q:
        ans = f"Total 30-day OpEx is ₹{ov['total_operating_cost']:,.2f} vs allocated budget of ₹{ov['total_budget_allocated']:,.2f} (Status: {ov['budget_compliance_status']})."
    else:
        ans = f"Facility total operating expenditure is ₹{ov['total_operating_cost']:,.2f} (₹{ov['cost_per_sqft']}/sq.ft). Identified potential savings total ₹{ov['opportunities_summary']['potential_savings']:,.2f} across {ov['opportunities_summary']['total_opportunities']} initiatives."

    return {
        "facility_id": facility_id,
        "query": query,
        "answer": ans,
        "cost_overview": ov
    }
