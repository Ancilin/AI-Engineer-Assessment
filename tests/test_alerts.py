import pytest
from src.alerts import AlertSimulator
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

@pytest.fixture
def simulator():
    return AlertSimulator()

def test_generate_payload(simulator):
    """Test generating Slack webhook JSON payload."""
    anomaly = {
        "ticket_id": "TKT-999",
        "severity": "CRITICAL",
        "anomaly_type": "SLA Breach",
        "category": "Technical",
        "priority": "Critical",
        "status": "Open",
        "agent_id": "AGT-01",
        "issue_summary": "Test Critical Outage",
        "reasons": ["Unresolved Critical ticket open for 30 hours."]
    }
    payload = simulator.generate_webhook_payload(anomaly, "slack")
    assert "attachments" in payload
    assert "TKT-999" in payload["attachments"][0]["title"]

def test_dispatch_critical_alerts(simulator):
    """Test dispatching batch critical anomaly alerts."""
    dispatched = simulator.dispatch_all_critical_anomalies()
    assert isinstance(dispatched, list)
    assert len(dispatched) > 0
    assert dispatched[0]["status"] == "SENT_SUCCESS"

def test_alert_history_api():
    """Test GET /alerts/history and POST /alerts/dispatch-critical endpoints."""
    post_res = client.post("/alerts/dispatch-critical")
    assert post_res.status_code == 200
    assert post_res.json()["dispatched_count"] > 0

    get_res = client.get("/alerts/history")
    assert get_res.status_code == 200
    assert get_res.json()["total_logs"] > 0
