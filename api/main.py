import os
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.db import DEFAULT_DB_PATH, execute_query
from src.ingest import ingest_csv_to_sqlite
from src.query_engine import QueryEngine
from src.anomalies import AnomalyDetector
from src.alerts import AlertSimulator

# Auto-ingest on app startup if DB does not exist or is empty
if not os.path.exists(DEFAULT_DB_PATH):
    ingest_csv_to_sqlite()

app = FastAPI(
    title="AI Support Ticket Analytics API",
    description="REST API for querying support tickets using natural language, detecting anomalies, and triggering alert notifications.",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Schemas
class QueryRequest(BaseModel):
    query: str = Field(..., description="Natural language question about ticket dataset")

class QueryResponse(BaseModel):
    question: str
    sql: str
    explanation: str
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    answer_summary: str
    success: bool
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    db_connected: bool
    total_tickets: int
    version: str

class AlertDispatchRequest(BaseModel):
    ticket_id: str
    channel: str = "Webhook (Slack)"
    destination: str = "https://api.example.com/webhook/incoming"

@app.get("/", tags=["General"])
def root():
    return {
        "message": "AI Support Ticket Analytics API is running.",
        "docs": "/docs",
        "endpoints": ["/health", "/query", "/anomalies", "/summary", "/tickets", "/alerts/dispatch-critical", "/alerts/history"]
    }

@app.get("/health", response_model=HealthResponse, tags=["General"])
def health_check():
    """System health check verifying database state and ticket count."""
    try:
        res = execute_query("SELECT COUNT(*) as count FROM tickets")
        total = res["rows"][0]["count"] if res["success"] and res["rows"] else 0
        return HealthResponse(
            status="healthy",
            db_connected=res["success"],
            total_tickets=total,
            version="1.1.0"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database health check failed: {str(e)}")

@app.post("/query", response_model=QueryResponse, tags=["NL Query Engine"])
def process_nl_query(req: QueryRequest):
    """
    Accepts a natural language question about support tickets and executes Text-to-SQL query.
    Returns SQL query, explanation, row data, and summary.
    """
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty.")
    
    engine = QueryEngine()
    result = engine.process_query(req.query)
    
    if not result["success"]:
        return QueryResponse(
            question=req.query,
            sql=result.get("sql", ""),
            explanation=result.get("explanation", ""),
            columns=[],
            rows=[],
            row_count=0,
            answer_summary=result.get("answer_summary", "Query processing failed."),
            success=False,
            error=result.get("error")
        )
        
    return QueryResponse(**result)

@app.get("/anomalies", tags=["Anomaly Detection"])
def get_anomalies(
    severity: Optional[str] = Query(None, description="Filter by severity: CRITICAL, HIGH, MEDIUM"),
    anomaly_type: Optional[str] = Query(None, description="Filter by anomaly type e.g., 'SLA Breach', 'Resolution Time Outlier'"),
    limit: int = Query(100, ge=1, le=500)
):
    """
    Detects statistical outliers, SLA breaches, response delays, and dissatisfaction anomalies across support tickets.
    """
    detector = AnomalyDetector()
    report = detector.run_all_checks()
    
    anomalies = report["anomalies"]
    if severity:
        anomalies = [a for a in anomalies if a["severity"].upper() == severity.upper()]
    if anomaly_type:
        anomalies = [a for a in anomalies if anomaly_type.lower() in a["anomaly_type"].lower()]

    anomalies = anomalies[:limit]

    return {
        "total_anomalies_found": report["total_anomalies_found"],
        "filtered_count": len(anomalies),
        "severity_counts": report["severity_counts"],
        "anomalies": anomalies
    }

@app.get("/summary", tags=["Dataset Metrics"])
def get_dataset_summary():
    """Returns high-level aggregate KPIs and ticket distribution summary."""
    sql = """
    SELECT 
        COUNT(*) as total_tickets,
        SUM(CASE WHEN status = 'Open' THEN 1 ELSE 0 END) as open_tickets,
        SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) as resolved_tickets,
        SUM(CASE WHEN status = 'Escalated' THEN 1 ELSE 0 END) as escalated_tickets,
        ROUND(AVG(response_time_hrs), 2) as avg_response_time_hrs,
        ROUND(AVG(resolution_time_hrs), 2) as avg_resolution_time_hrs,
        ROUND(AVG(customer_rating), 2) as avg_customer_rating
    FROM tickets
    """
    res = execute_query(sql)
    if not res["success"] or not res.get("rows"):
        ingest_csv_to_sqlite()
        res = execute_query(sql)
        if not res["success"] or not res.get("rows"):
            raise HTTPException(status_code=500, detail="Failed to fetch dataset summary.")
    
    summary = res["rows"][0]
    
    # Priority breakdown
    prio_res = execute_query("SELECT priority, COUNT(*) as count FROM tickets GROUP BY priority")
    prio_breakdown = {r["priority"]: r["count"] for r in prio_res["rows"]} if prio_res["success"] else {}

    # Category breakdown
    cat_res = execute_query("SELECT category, COUNT(*) as count FROM tickets GROUP BY category")
    cat_breakdown = {r["category"]: r["count"] for r in cat_res["rows"]} if cat_res["success"] else {}

    return {
        "kpis": summary,
        "priority_breakdown": prio_breakdown,
        "category_breakdown": cat_breakdown
    }

@app.get("/tickets", tags=["Ticket Explorer"])
def get_tickets(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """Paginated ticket search and filtering."""
    where_clauses = []
    params = []

    if status:
        where_clauses.append("status = ?")
        params.append(status)
    if priority:
        where_clauses.append("priority = ?")
        params.append(priority)
    if category:
        where_clauses.append("category = ?")
        params.append(category)
    if agent_id:
        where_clauses.append("agent_id = ?")
        params.append(agent_id)

    where_str = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    offset = (page - 1) * page_size

    count_sql = f"SELECT COUNT(*) as total FROM tickets{where_str}"
    data_sql = f"SELECT * FROM tickets{where_str} ORDER BY ticket_id ASC LIMIT {page_size} OFFSET {offset}"

    from src.db import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(count_sql, params)
    total_count = cursor.fetchone()["total"]

    cursor.execute(data_sql, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": (total_count + page_size - 1) // page_size,
        "tickets": rows
    }

@app.post("/alerts/dispatch-critical", tags=["Alert Simulator"])
def dispatch_critical_alerts(channel: str = "Webhook (Slack)", destination: str = "https://api.example.com/webhook/incoming"):
    """Scans for all CRITICAL anomalies and triggers simulated Webhook/Email alert notifications."""
    simulator = AlertSimulator()
    dispatched = simulator.dispatch_all_critical_anomalies(channel, destination)
    return {
        "message": f"Successfully dispatched {len(dispatched)} CRITICAL alert notifications.",
        "dispatched_count": len(dispatched),
        "alerts": dispatched
    }

@app.get("/alerts/history", tags=["Alert Simulator"])
def get_alert_history(limit: int = Query(50, ge=1, le=200)):
    """Returns log trail of all dispatched alert notifications."""
    simulator = AlertSimulator()
    history = simulator.get_alert_history(limit)
    return {
        "total_logs": len(history),
        "logs": history
    }
