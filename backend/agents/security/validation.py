from datetime import datetime
from typing import Dict, List, Tuple


def validate_event(event: Dict) -> Tuple[bool, List[str]]:
    """Validate security event payload for completeness and field constraints."""
    errors = []
    if not event.get("facility_id"):
        errors.append("facility_id is required")
    if not event.get("zone"):
        errors.append("zone is required")
    if not event.get("event_type"):
        errors.append("event_type is required")
    if not event.get("description"):
        errors.append("description is required")
    ts = event.get("timestamp")
    if not ts:
        errors.append("timestamp is required")
    else:
        try:
            datetime.fromisoformat(ts)
        except ValueError:
            errors.append("timestamp must be valid ISO format")
    return (len(errors) == 0, errors)
