import pytest
from src.anomalies import AnomalyDetector

@pytest.fixture
def detector():
    return AnomalyDetector()

def test_run_all_checks(detector):
    """Verify anomaly detector returns structured report with severity counts."""
    report = detector.run_all_checks()
    assert "total_anomalies_found" in report
    assert report["total_anomalies_found"] > 0
    assert "CRITICAL" in report["severity_counts"]
    assert "HIGH" in report["severity_counts"]

def test_sla_breaches(detector):
    """Verify SLA breach detection flags tickets."""
    breaches = detector.detect_sla_breaches()
    assert isinstance(breaches, list)
    for item in breaches:
        assert "ticket_id" in item
        assert item["severity"] in ["CRITICAL", "HIGH", "MEDIUM"]

def test_resolution_outliers(detector):
    """Verify resolution time outlier detection."""
    outliers = detector.detect_resolution_time_outliers()
    assert isinstance(outliers, list)
    for item in outliers:
        assert item["metric"] == "resolution_time_hrs"
