from datetime import datetime
from typing import List, Tuple


def validate_record(record: dict) -> Tuple[bool, List[str]]:
    """Validate an incoming occupancy record for schema and value integrity."""
    errors = []
    if not record.get("facility_id"):
        errors.append("facility_id is required")
    if not record.get("zone"):
        errors.append("zone name is required")
    count = record.get("occupancy_count")
    if count is None or not isinstance(count, (int, float)) or count < 0:
        errors.append("occupancy_count must be a non-negative number")
    cap = record.get("capacity")
    if cap is None or not isinstance(cap, (int, float)) or cap <= 0:
        errors.append("capacity must be a positive integer")
    ts = record.get("timestamp")
    if not ts:
        errors.append("timestamp is required")
    else:
        try:
            datetime.fromisoformat(ts)
        except ValueError:
            errors.append("timestamp must be valid ISO format")
    return (len(errors) == 0, errors)
