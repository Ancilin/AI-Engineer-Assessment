import os
import math
from typing import Dict, Any, List, Optional
from src.db import execute_query, DEFAULT_DB_PATH

class AnomalyDetector:
    """Detects statistical outliers, SLA breaches, and anomalous patterns in support tickets."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path

    def run_all_checks(self) -> Dict[str, Any]:
        """Runs all anomaly detection checks and returns consolidated diagnostic report."""
        resolution_anomalies = self.detect_resolution_time_outliers()
        sla_violations = self.detect_sla_breaches()
        response_spikes = self.detect_response_time_spikes()
        rating_anomalies = self.detect_rating_anomalies()

        all_flagged = (
            resolution_anomalies +
            sla_violations +
            response_spikes +
            rating_anomalies
        )

        # Deduplicate tickets by ticket_id while aggregating anomaly reasons
        unique_tickets: Dict[str, Dict[str, Any]] = {}
        for item in all_flagged:
            tid = item["ticket_id"]
            if tid not in unique_tickets:
                unique_tickets[tid] = item
            else:
                # Merge reasons if flagged under multiple rules
                unique_tickets[tid]["reasons"].extend(item["reasons"])
                # Elevate severity if higher
                if item["severity"] == "CRITICAL":
                    unique_tickets[tid]["severity"] = "CRITICAL"

        consolidated = list(unique_tickets.values())
        consolidated.sort(key=lambda x: (x["severity"] != "CRITICAL", x["severity"] != "HIGH", x["ticket_id"]))

        severity_counts = {
            "CRITICAL": sum(1 for t in consolidated if t["severity"] == "CRITICAL"),
            "HIGH": sum(1 for t in consolidated if t["severity"] == "HIGH"),
            "MEDIUM": sum(1 for t in consolidated if t["severity"] == "MEDIUM"),
        }

        return {
            "total_anomalies_found": len(consolidated),
            "severity_counts": severity_counts,
            "resolution_time_outliers_count": len(resolution_anomalies),
            "sla_violations_count": len(sla_violations),
            "response_time_spikes_count": len(response_spikes),
            "rating_anomalies_count": len(rating_anomalies),
            "anomalies": consolidated
        }

    def detect_resolution_time_outliers(self, threshold_factor: float = 1.5) -> List[Dict[str, Any]]:
        """
        Detects resolution time outliers using Interquartile Range (IQR) per category.
        Flagged if resolution_time_hrs > Q3 + threshold_factor * IQR.
        """
        # Fetch category distribution statistics
        stats_sql = """
        SELECT category, resolution_time_hrs 
        FROM tickets 
        WHERE status = 'Resolved' AND resolution_time_hrs IS NOT NULL
        ORDER BY category, resolution_time_hrs
        """
        result = execute_query(stats_sql, self.db_path)
        if not result["success"] or not result["rows"]:
            return []

        # Group resolution times by category
        cat_times: Dict[str, List[float]] = {}
        for r in result["rows"]:
            cat = r["category"]
            val = float(r["resolution_time_hrs"])
            cat_times.setdefault(cat, []).append(val)

        cat_thresholds: Dict[str, float] = {}
        for cat, times in cat_times.items():
            if len(times) < 4:
                continue
            times.sort()
            n = len(times)
            q1 = times[n // 4]
            q3 = times[(3 * n) // 4]
            iqr = q3 - q1
            cat_thresholds[cat] = q3 + (threshold_factor * iqr)

        # Query all resolved tickets exceeding category outlier thresholds
        anomalies = []
        all_resolved = execute_query(
            "SELECT * FROM tickets WHERE status = 'Resolved' AND resolution_time_hrs IS NOT NULL",
            self.db_path
        )["rows"]

        for t in all_resolved:
            cat = t["category"]
            res_time = float(t["resolution_time_hrs"])
            cutoff = cat_thresholds.get(cat, 30.0)

            if res_time > cutoff:
                severity = "CRITICAL" if res_time > (cutoff * 1.5) else "HIGH" if res_time > (cutoff * 1.2) else "MEDIUM"
                anomalies.append({
                    "ticket_id": t["ticket_id"],
                    "category": t["category"],
                    "priority": t["priority"],
                    "status": t["status"],
                    "agent_id": t["agent_id"],
                    "value": res_time,
                    "metric": "resolution_time_hrs",
                    "threshold": round(cutoff, 2),
                    "severity": severity,
                    "anomaly_type": "Resolution Time Outlier",
                    "reasons": [f"Resolution time ({res_time} hrs) exceeds statistical category threshold ({round(cutoff, 2)} hrs)."],
                    "issue_summary": t["issue_summary"]
                })

        return anomalies

    def detect_sla_breaches(self, sla_hours: float = 24.0) -> List[Dict[str, Any]]:
        """
        Detects SLA breaches:
        - Unresolved High/Critical tickets with age > sla_hours
        - Resolved Critical tickets with resolution time > sla_hours
        """
        sql = """
        SELECT * FROM tickets
        WHERE (priority IN ('Critical', 'High') AND status != 'Resolved')
           OR (priority = 'Critical' AND resolution_time_hrs > ?)
        """
        res = execute_query(sql, self.db_path)
        if not res["success"]:
            return []

        anomalies = []
        for t in res["rows"]:
            is_unresolved = t["status"] != "Resolved"
            res_time = float(t["resolution_time_hrs"]) if t["resolution_time_hrs"] is not None else None
            
            reasons = []
            if is_unresolved:
                reasons.append(f"Unresolved {t['priority']} priority ticket requires immediate attention.")
                severity = "CRITICAL" if t["priority"] == "Critical" else "HIGH"
            else:
                reasons.append(f"Critical ticket resolved in {res_time} hrs, exceeding {sla_hours}h SLA limit.")
                severity = "HIGH"

            anomalies.append({
                "ticket_id": t["ticket_id"],
                "category": t["category"],
                "priority": t["priority"],
                "status": t["status"],
                "agent_id": t["agent_id"],
                "value": res_time if res_time is not None else 0.0,
                "metric": "sla_breach",
                "threshold": sla_hours,
                "severity": severity,
                "anomaly_type": "SLA Breach",
                "reasons": reasons,
                "issue_summary": t["issue_summary"]
            })

        return anomalies

    def detect_response_time_spikes(self, spike_threshold_hrs: float = 8.0) -> List[Dict[str, Any]]:
        """Detects tickets with abnormally high initial agent response times."""
        sql = "SELECT * FROM tickets WHERE response_time_hrs > ? ORDER BY response_time_hrs DESC"
        res = execute_query(sql, self.db_path)
        if not res["success"]:
            return []

        anomalies = []
        for t in res["rows"]:
            resp_time = float(t["response_time_hrs"])
            severity = "CRITICAL" if resp_time > 15.0 else "HIGH" if resp_time > 10.0 else "MEDIUM"
            anomalies.append({
                "ticket_id": t["ticket_id"],
                "category": t["category"],
                "priority": t["priority"],
                "status": t["status"],
                "agent_id": t["agent_id"],
                "value": resp_time,
                "metric": "response_time_hrs",
                "threshold": spike_threshold_hrs,
                "severity": severity,
                "anomaly_type": "Response Time Spike",
                "reasons": [f"First response delayed by {resp_time} hrs (Threshold: {spike_threshold_hrs} hrs)."],
                "issue_summary": t["issue_summary"]
            })
        return anomalies

    def detect_rating_anomalies(self) -> List[Dict[str, Any]]:
        """
        Detects customer rating anomalies:
        - Low customer rating (1 or 2) on tickets resolved within standard timeframe.
        """
        sql = "SELECT * FROM tickets WHERE status = 'Resolved' AND customer_rating IN (1, 2) ORDER BY customer_rating ASC"
        res = execute_query(sql, self.db_path)
        if not res["success"]:
            return []

        anomalies = []
        for t in res["rows"]:
            rating = int(t["customer_rating"])
            anomalies.append({
                "ticket_id": t["ticket_id"],
                "category": t["category"],
                "priority": t["priority"],
                "status": t["status"],
                "agent_id": t["agent_id"],
                "value": rating,
                "metric": "customer_rating",
                "threshold": 3,
                "severity": "HIGH" if rating == 1 else "MEDIUM",
                "anomaly_type": "Customer Dissatisfaction Anomaly",
                "reasons": [f"Ticket resolved but received low satisfaction rating of {rating}/5."],
                "issue_summary": t["issue_summary"]
            })
        return anomalies
