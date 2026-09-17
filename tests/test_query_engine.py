import pytest
from src.query_engine import QueryEngine

@pytest.fixture
def engine():
    return QueryEngine()

def test_open_tickets_query(engine):
    """Test 'How many tickets are currently open?'"""
    res = engine.process_query("How many tickets are currently open?")
    assert res["success"] is True
    assert res["row_count"] >= 1
    assert "count" in res["sql"].lower()

def test_agent_query(engine):
    """Test 'Which agent resolved the most tickets this month?'"""
    res = engine.process_query("Which agent resolved the most tickets this month?")
    assert res["success"] is True
    assert res["row_count"] >= 1
    assert "agent_id" in res["columns"]

def test_critical_tickets_query(engine):
    """Test 'Show me all Critical tickets not resolved within 12 hours.'"""
    res = engine.process_query("Show me all Critical tickets not resolved within 12 hours.")
    assert res["success"] is True
    assert res["row_count"] >= 0

def test_avg_rating_query(engine):
    """Test 'What is the average customer rating for Technical category tickets?'"""
    res = engine.process_query("What is the average customer rating for Technical category tickets?")
    assert res["success"] is True
    assert res["row_count"] == 1

def test_security_guardrail(engine):
    """Verify that non-SELECT statements like DROP or DELETE are rejected."""
    res = engine.process_query("DROP TABLE tickets;")
    # Either fallback SQL returns a harmless SELECT or query execution rejects non-SELECT
    if res["success"]:
        assert res["sql"].upper().startswith("SELECT")
    else:
        assert "Security" in res["error"] or "Only SELECT" in res["error"]
