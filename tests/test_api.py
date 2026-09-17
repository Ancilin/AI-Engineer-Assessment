import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_health_endpoint():
    """Test GET /health"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["db_connected"] is True
    assert data["total_tickets"] == 500

def test_query_endpoint():
    """Test POST /query"""
    response = client.post("/query", json={"query": "How many open tickets are there?"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["row_count"] >= 1

def test_anomalies_endpoint():
    """Test GET /anomalies"""
    response = client.get("/anomalies?severity=CRITICAL")
    assert response.status_code == 200
    data = response.json()
    assert "anomalies" in data
    for item in data["anomalies"]:
        assert item["severity"] == "CRITICAL"

def test_summary_endpoint():
    """Test GET /summary"""
    response = client.get("/summary")
    assert response.status_code == 200
    data = response.json()
    assert "kpis" in data
    assert data["kpis"]["total_tickets"] == 500

def test_tickets_endpoint():
    """Test GET /tickets with pagination"""
    response = client.get("/tickets?page=1&page_size=10&category=Billing")
    assert response.status_code == 200
    data = response.json()
    assert data["page_size"] == 10
    assert len(data["tickets"]) <= 10
