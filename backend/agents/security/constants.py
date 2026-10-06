# Severity weighting matrix for risk index computation
SEVERITY_WEIGHTS = {
    "INFO": 10,
    "WARNING": 35,
    "HIGH": 75,
    "CRITICAL": 100
}

EVENT_BASE_RISKS = {
    "UNAUTHORIZED_ACCESS": {"severity": "HIGH", "risk_level": "HIGH", "score": 80},
    "DOOR_FORCED":         {"severity": "CRITICAL", "risk_level": "CRITICAL", "score": 95},
    "TAILGATING":           {"severity": "WARNING", "risk_level": "MEDIUM", "score": 45},
    "AFTER_HOURS_ENTRY":   {"severity": "HIGH", "risk_level": "HIGH", "score": 70},
    "CCTV_ANOMALY":        {"severity": "CRITICAL", "risk_level": "HIGH", "score": 85},
    "BADGE_MISUSE":        {"severity": "WARNING", "risk_level": "MEDIUM", "score": 50},
}
