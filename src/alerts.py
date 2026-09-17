import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from src.db import execute_query, get_db_connection, DEFAULT_DB_PATH
from src.anomalies import AnomalyDetector

logger = logging.getLogger(__name__)

# Ensure alert log table exists in database
def init_alert_db(db_path: str = DEFAULT_DB_PATH):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alert_logs (
        alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        ticket_id TEXT NOT NULL,
        severity TEXT NOT NULL,
        channel TEXT NOT NULL,
        destination TEXT NOT NULL,
        payload TEXT NOT NULL,
        status TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()

init_alert_db()

class AlertSimulator:
    """Simulates sending instant Webhook (Slack/Teams/PagerDuty) and Email alert notifications for critical ticket anomalies."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        init_alert_db(db_path)

    def generate_webhook_payload(self, anomaly: Dict[str, Any], channel_type: str = "slack") -> Dict[str, Any]:
        """Generates standard Webhook payload JSON formatted for Slack/Teams/PagerDuty."""
        tid = anomaly["ticket_id"]
        severity = anomaly["severity"]
        anomaly_type = anomaly["anomaly_type"]
        summary = anomaly.get("issue_summary", "")
        reasons = " | ".join(anomaly.get("reasons", []))

        if channel_type.lower() == "slack":
            color = "#da3633" if severity == "CRITICAL" else "#d9822b"
            return {
                "attachments": [
                    {
                        "color": color,
                        "title": f"🚨 [{severity}] Support Ticket Alert: {tid}",
                        "text": f"**Anomaly Type:** {anomaly_type}\n**Issue:** {summary}\n**Category:** {anomaly.get('category')} | **Priority:** {anomaly.get('priority')}",
                        "fields": [
                            {"title": "Assigned Agent", "value": str(anomaly.get("agent_id")), "short": True},
                            {"title": "Current Status", "value": str(anomaly.get("status")), "short": True},
                            {"title": "Diagnostic Reasons", "value": reasons, "short": False}
                        ],
                        "footer": "AI Support Ticket Alert System",
                        "ts": int(datetime.now().timestamp())
                    }
                ]
            }
        else: # Generic Webhook / Teams / PagerDuty payload format
            return {
                "event_type": "TICKET_ANOMALY_ALERT",
                "ticket_id": tid,
                "severity": severity,
                "anomaly_type": anomaly_type,
                "category": anomaly.get("category"),
                "priority": anomaly.get("priority"),
                "status": anomaly.get("status"),
                "agent_id": anomaly.get("agent_id"),
                "summary": summary,
                "reasons": anomaly.get("reasons", []),
                "timestamp": datetime.now().isoformat()
            }

    def dispatch_alert(
        self,
        anomaly: Dict[str, Any],
        channel: str = "Webhook (Slack/Teams)",
        destination: str = "https://api.example.com/webhook/incoming"
    ) -> Dict[str, Any]:
        """Dispatches simulated alert notification and records log in database."""
        payload = self.generate_webhook_payload(anomaly, "slack" if "slack" in channel.lower() else "generic")
        payload_str = json.dumps(payload)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO alert_logs (timestamp, ticket_id, severity, channel, destination, payload, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (now_str, anomaly["ticket_id"], anomaly["severity"], channel, destination, payload_str, "SENT_SUCCESS"))
        
        alert_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return {
            "alert_id": alert_id,
            "timestamp": now_str,
            "ticket_id": anomaly["ticket_id"],
            "severity": anomaly["severity"],
            "channel": channel,
            "destination": destination,
            "status": "SENT_SUCCESS",
            "payload": payload
        }

    def dispatch_all_critical_anomalies(
        self,
        channel: str = "Webhook (Slack)",
        destination: str = "https://api.example.com/webhook/incoming"
    ) -> List[Dict[str, Any]]:
        """Scans for all CRITICAL severity anomalies and dispatches alerts."""
        detector = AnomalyDetector(self.db_path)
        report = detector.run_all_checks()
        critical_anomalies = [a for a in report["anomalies"] if a["severity"] == "CRITICAL"]

        dispatched = []
        for anomaly in critical_anomalies[:10]: # Limit top 10 for batch test
            res = self.dispatch_alert(anomaly, channel, destination)
            dispatched.append(res)

        return dispatched

    def get_alert_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves audit trail of dispatched alert notifications."""
        sql = f"SELECT * FROM alert_logs ORDER BY alert_id DESC LIMIT {limit}"
        res = execute_query(sql, self.db_path)
        return res["rows"] if res["success"] else []
