"""Graduated alerts system for training metrics."""

from typing import Any


class Alert:
    """Training alert with severity and message."""

    def __init__(
        self,
        severity: str,
        category: str,
        metric: str,
        value: float | str,
        threshold: float | str,
        message: str,
    ):
        """Initialize alert.

        Args:
            severity: "warning" or "alarm"
            category: Alert category (recovery, load, distribution, durability, consistency)
            metric: Metric name
            value: Current metric value
            threshold: Threshold value that triggered alert
            message: Alert message
        """
        self.severity = severity
        self.category = category
        self.metric = metric
        self.value = value
        self.threshold = threshold
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "severity": self.severity,
            "category": self.category,
            "metric": self.metric,
            "value": self.value,
            "threshold": self.threshold,
            "message": self.message,
        }


def generate_alerts(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate graduated alerts based on metric thresholds.

    Args:
        metrics: Dictionary containing all calculated metrics

    Returns:
        List of alert dictionaries sorted by severity
    """
    alerts: list[Alert] = []

    # Recovery Index alerts
    ri = metrics.get("recovery_index")
    if ri is not None:
        if ri < 0.6:
            alerts.append(
                Alert(
                    severity="alarm",
                    category="recovery",
                    metric="recovery_index",
                    value=round(ri, 2),
                    threshold=0.6,
                    message="Recovery Index critically low - deload required",
                )
            )
        elif ri < 0.8:
            alerts.append(
                Alert(
                    severity="warning",
                    category="recovery",
                    metric="recovery_index",
                    value=round(ri, 2),
                    threshold=0.8,
                    message="Recovery Index low - consider reducing intensity",
                )
            )

    # ACWR alerts
    acwr = metrics.get("acwr")
    if acwr is not None:
        if acwr < 0.8:
            alerts.append(
                Alert(
                    severity="warning",
                    category="load",
                    metric="acwr",
                    value=round(acwr, 2),
                    threshold=0.8,
                    message="ACWR low - training load may be insufficient",
                )
            )
        elif acwr > 1.5:
            alerts.append(
                Alert(
                    severity="alarm",
                    category="load",
                    metric="acwr",
                    value=round(acwr, 2),
                    threshold=1.5,
                    message="ACWR critically high - high injury risk",
                )
            )
        elif acwr > 1.3:
            alerts.append(
                Alert(
                    severity="warning",
                    category="load",
                    metric="acwr",
                    value=round(acwr, 2),
                    threshold=1.3,
                    message="ACWR elevated - over-reaching risk",
                )
            )

    # Monotony alerts
    monotony = metrics.get("monotony")
    if monotony is not None:
        if monotony > 2.5:
            alerts.append(
                Alert(
                    severity="alarm",
                    category="load",
                    metric="monotony",
                    value=round(monotony, 2),
                    threshold=2.5,
                    message="Training monotony too high - add variety",
                )
            )
        elif monotony > 2.3:
            alerts.append(
                Alert(
                    severity="warning",
                    category="load",
                    metric="monotony",
                    value=round(monotony, 2),
                    threshold=2.3,
                    message="Training monotony approaching limit",
                )
            )

    # Strain alerts
    strain = metrics.get("strain")
    if strain is not None and strain > 3500:
        alerts.append(
            Alert(
                severity="alarm",
                category="load",
                metric="strain",
                value=round(strain, 1),
                threshold=3500,
                message="Training strain critically high",
            )
        )

    # Polarization Index alerts
    pi_7d = metrics.get("polarization_index_7d")
    if pi_7d is not None and pi_7d < 1.5:
        alerts.append(
            Alert(
                severity="warning",
                category="distribution",
                metric="polarization_index_7d",
                value=round(pi_7d, 2),
                threshold=1.5,
                message="Training becoming threshold-heavy (7d) - consider more polarization",
            )
        )

    # TID Drift alerts
    tid_drift = metrics.get("tid_drift")
    if tid_drift == "acute_depolarization":
        alerts.append(
            Alert(
                severity="warning",
                category="distribution",
                metric="tid_drift",
                value=tid_drift,
                threshold="acute_depolarization",
                message="Acute depolarization detected - high Z2 load this week",
            )
        )

    # Durability alerts (mean decoupling)
    decoupling_7d = metrics.get("durability_7d_mean_decoupling")
    if decoupling_7d is not None:
        abs_decoupling = abs(decoupling_7d)
        if abs_decoupling > 10:
            alerts.append(
                Alert(
                    severity="warning",
                    category="durability",
                    metric="durability_7d_mean_decoupling",
                    value=round(abs_decoupling, 1),
                    threshold=10.0,
                    message="Poor aerobic durability (7d avg) - focus on aerobic base building",
                )
            )

    # Consistency alerts
    consistency = metrics.get("consistency_index")
    if consistency is not None:
        if consistency < 0.5:
            alerts.append(
                Alert(
                    severity="warning",
                    category="consistency",
                    metric="consistency_index",
                    value=round(consistency, 2),
                    threshold=0.5,
                    message="Low training consistency - aim for more regular sessions",
                )
            )

    # Sort alerts by severity (alarm first, then warning)
    severity_order = {"alarm": 0, "warning": 1}
    sorted_alerts = sorted(alerts, key=lambda a: severity_order.get(a.severity, 2))

    return [alert.to_dict() for alert in sorted_alerts]


def count_alerts_by_severity(alerts: list[dict[str, Any]]) -> dict[str, int]:
    """Count alerts by severity level.

    Args:
        alerts: List of alert dictionaries

    Returns:
        Dictionary with counts by severity
    """
    counts = {"alarm": 0, "warning": 0}

    for alert in alerts:
        severity = alert.get("severity", "")
        if severity in counts:
            counts[severity] += 1

    return counts