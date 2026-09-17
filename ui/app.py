import sys
import os
import json
import pandas as pd
import streamlit as st

# Add root project directory to sys.path so modules import seamlessly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db import execute_query, DEFAULT_DB_PATH
from src.query_engine import QueryEngine
from src.anomalies import AnomalyDetector
from src.alerts import AlertSimulator
from src.ingest import ingest_csv_to_sqlite

# Page configuration
st.set_page_config(
    page_title="AI Support Ticket Intelligence Platform",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for rich dark theme aesthetics & glassmorphism
st.markdown("""
<style>
    /* Dark Theme Core Styling */
    .main {
        background-color: #0e1117;
        color: #e0e6ed;
    }
    .stApp {
        background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
    }
    
    /* Header Card Styling */
    .header-card {
        background: rgba(22, 27, 34, 0.85);
        border: 1px solid rgba(48, 54, 61, 0.8);
        border-radius: 14px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.45);
        backdrop-filter: blur(10px);
    }
    
    /* KPI Metric Cards */
    .metric-card {
        background: linear-gradient(145deg, #1c2128, #161b22);
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 14px rgba(0,0,0,0.3);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: #58a6ff;
    }
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #58a6ff;
        margin-top: 6px;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-weight: 600;
    }
    
    /* Badges */
    .badge-critical {
        background: linear-gradient(135deg, #da3633 0%, #b82522 100%);
        color: white;
        padding: 5px 12px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.8rem;
        letter-spacing: 0.04em;
    }
    .badge-high {
        background: linear-gradient(135deg, #d9822b 0%, #b36417 100%);
        color: white;
        padding: 5px 12px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.8rem;
        letter-spacing: 0.04em;
    }
    .badge-medium {
        background: linear-gradient(135deg, #2da44e 0%, #1e7e34 100%);
        color: white;
        padding: 5px 12px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.8rem;
        letter-spacing: 0.04em;
    }
    
    /* Step Box */
    .step-box {
        background: rgba(13, 17, 23, 0.9);
        border: 1px solid #30363d;
        border-left: 5px solid #58a6ff;
        border-radius: 10px;
        padding: 18px;
        margin-bottom: 16px;
    }
    .step-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #58a6ff;
        margin-bottom: 6px;
    }
</style>
""", unsafe_allow_html=True)

# Ensure database exists
if not os.path.exists(DEFAULT_DB_PATH):
    with st.spinner("Initializing SQLite Database from CSV..."):
        ingest_csv_to_sqlite()

# Sidebar Navigation
st.sidebar.image("https://img.icons8.com/color/96/artificial-intelligence.png", width=64)
st.sidebar.title("AI Ticket Control Center")
st.sidebar.caption("DOTMappers AI System Sprint Assessment")

navigation = st.sidebar.radio(
    "Navigate",
    ["📊 Executive Dashboard", "💬 Natural Language Query", "🚨 Anomaly Hub", "🔍 Ticket Explorer", "🎥 Video Tutorial & User Guide"],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.info("""
**System Architecture:**
- **Backend:** FastAPI + SQLite
- **LLM Core:** Groq / Ollama / Smart Fallback
- **Dataset:** 500 Support Tickets
""")

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
HERO_BANNER = os.path.join(ASSETS_DIR, "hero_banner.png")
ANOMALY_BANNER = os.path.join(ASSETS_DIR, "anomaly_banner.png")
TUTORIAL_BANNER = os.path.join(ASSETS_DIR, "tutorial_banner.png")

# ==========================================
# TAB 1: EXECUTIVE DASHBOARD
# ==========================================
if navigation == "📊 Executive Dashboard":
    if os.path.exists(HERO_BANNER):
        st.image(HERO_BANNER, use_container_width=True)
    
    st.markdown("""
    <div class="header-card">
        <h1>📊 Support Ticket Intelligence Dashboard</h1>
        <p style="color: #8b949e; margin-bottom: 0;">Real-time KPIs, ticket resolution metrics, and operational performance insights.</p>
    </div>
    """, unsafe_allow_html=True)

    # Fetch aggregate stats
    kpi_query = """
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN status = 'Open' THEN 1 ELSE 0 END) as open_cnt,
        SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) as resolved_cnt,
        SUM(CASE WHEN status = 'Escalated' THEN 1 ELSE 0 END) as escalated_cnt,
        ROUND(AVG(response_time_hrs), 2) as avg_resp,
        ROUND(AVG(resolution_time_hrs), 2) as avg_resol,
        ROUND(AVG(customer_rating), 2) as avg_rating
    FROM tickets
    """
    kpi_data = execute_query(kpi_query)["rows"][0]

    # KPI Cards Row
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Tickets</div>
            <div class="metric-value">{kpi_data['total']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Open Tickets</div>
            <div class="metric-value" style="color: #f0883e;">{kpi_data['open_cnt']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Resolved</div>
            <div class="metric-value" style="color: #3fb950;">{kpi_data['resolved_cnt']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Avg Resolution Time</div>
            <div class="metric-value" style="color: #a5d6ff;">{kpi_data['avg_resol']}h</div>
        </div>
        """, unsafe_allow_html=True)
    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Avg Customer Rating</div>
            <div class="metric-value" style="color: #e3b341;">⭐ {kpi_data['avg_rating']}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Charts Row 1
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Tickets by Category & Priority")
        cat_prio_res = execute_query("SELECT category, priority, COUNT(*) as count FROM tickets GROUP BY category, priority")
        if cat_prio_res["success"]:
            df_cp = pd.DataFrame(cat_prio_res["rows"])
            pivot_df = df_cp.pivot(index="category", columns="priority", values="count").fillna(0)
            st.bar_chart(pivot_df)

    with c2:
        st.subheader("Ticket Status Distribution")
        status_res = execute_query("SELECT status, COUNT(*) as count FROM tickets GROUP BY status")
        if status_res["success"]:
            df_status = pd.DataFrame(status_res["rows"])
            st.bar_chart(df_status.set_index("status"))

    st.markdown("---")

    # Agent Performance Table
    st.subheader("👨‍💻 Top Support Agent Performance")
    agent_res = execute_query("""
    SELECT 
        agent_id,
        COUNT(*) as total_tickets,
        SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) as resolved_tickets,
        ROUND(AVG(customer_rating), 2) as avg_rating,
        ROUND(AVG(resolution_time_hrs), 2) as avg_resolution_hrs
    FROM tickets
    WHERE agent_id IS NOT NULL
    GROUP BY agent_id
    ORDER BY resolved_tickets DESC
    LIMIT 10
    """)
    if agent_res["success"]:
        st.dataframe(pd.DataFrame(agent_res["rows"]), use_container_width=True)

# ==========================================
# TAB 2: NATURAL LANGUAGE QUERY INTERFACE
# ==========================================
elif navigation == "💬 Natural Language Query":
    st.markdown("""
    <div class="header-card">
        <h1>💬 AI Natural Language Ticket Query Engine</h1>
        <p style="color: #8b949e; margin-bottom: 0;">Ask any question about support tickets in plain English. The AI generates and executes SQL in real-time.</p>
    </div>
    """, unsafe_allow_html=True)

    # Sample Quick Queries
    st.markdown("##### 💡 Try these sample questions:")
    sample_queries = [
        "How many tickets are currently open?",
        "Which agent resolved the most tickets this month?",
        "Show me all Critical tickets not resolved within 12 hours.",
        "What is the average customer rating for Technical category tickets?",
        "Are there any anomalies in resolution times this week?",
        "Which agent has the lowest average customer rating?"
    ]

    cols = st.columns(3)
    selected_sample = None
    for i, sq in enumerate(sample_queries):
        if cols[i % 3].button(sq, key=f"sq_{i}"):
            selected_sample = sq

    st.markdown("<br>", unsafe_allow_html=True)

    # Query Input Box
    user_input = st.text_input(
        "Ask a question about ticket data:",
        value=selected_sample if selected_sample else "",
        placeholder="e.g. How many unresolved critical tickets are there?"
    )

    if user_input:
        with st.spinner("Processing natural language question with AI..."):
            engine = QueryEngine()
            response = engine.process_query(user_input)

        if response["success"]:
            st.success(f"**Answer:** {response['answer_summary']}")
            
            # SQL Code accordion
            with st.expander("🔍 View Generated SQL Query & Logic", expanded=True):
                st.code(response["sql"], language="sql")
                st.caption(f"**Explanation:** {response['explanation']}")

            # Tabular Output
            st.markdown(f"##### 📋 Query Results ({response['row_count']} rows)")
            if response["rows"]:
                df_res = pd.DataFrame(response["rows"])
                st.dataframe(df_res, use_container_width=True)

                # Auto Chart if numeric columns present
                num_cols = df_res.select_dtypes(include=['number']).columns.tolist()
                str_cols = df_res.select_dtypes(include=['object']).columns.tolist()
                if str_cols and num_cols and len(df_res) <= 30 and len(df_res) > 1:
                    st.markdown("##### 📈 Data Visualization")
                    st.bar_chart(df_res.set_index(str_cols[0])[num_cols[0]])
            else:
                st.info("No records returned for this query.")
        else:
            st.error(f"Error processing query: {response['error']}")

# ==========================================
# TAB 3: ANOMALY HUB & ALERT SIMULATOR
# ==========================================
elif navigation == "🚨 Anomaly Hub":
    if os.path.exists(ANOMALY_BANNER):
        st.image(ANOMALY_BANNER, use_container_width=True)

    st.markdown("""
    <div class="header-card">
        <h1>🚨 Ticket Anomaly & SLA Breach Detection Hub</h1>
        <p style="color: #8b949e; margin-bottom: 0;">Statistical outlier analysis, SLA breach flagging, and customer dissatisfaction warnings.</p>
    </div>
    """, unsafe_allow_html=True)

    detector = AnomalyDetector()
    report = detector.run_all_checks()

    # Severity KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Anomalies</div>
            <div class="metric-value">{report['total_anomalies_found']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Critical Alerts</div>
            <div class="metric-value" style="color: #da3633;">{report['severity_counts']['CRITICAL']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">High Alerts</div>
            <div class="metric-value" style="color: #d9822b;">{report['severity_counts']['HIGH']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Medium Alerts</div>
            <div class="metric-value" style="color: #3fb950;">{report['severity_counts']['MEDIUM']}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Automated Webhook Alert Dispatcher Section
    with st.expander("🔔 Automated Alert & Notification Center (Slack / Teams / PagerDuty)", expanded=False):
        st.markdown("##### 🚀 Dispatch Automated Webhook Payload for Critical Ticket Anomalies")
        alert_col1, alert_col2 = st.columns(2)
        with alert_col1:
            dest_channel = st.selectbox("Target Notification Channel", ["Slack Webhook", "Microsoft Teams Webhook", "PagerDuty Event API"])
            dest_url = st.text_input("Webhook Destination URL", value="https://api.example.com/webhook/incoming")
        with alert_col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("⚡ Dispatch Instant Critical Alerts Payload", use_container_width=True):
                simulator = AlertSimulator()
                dispatched = simulator.dispatch_all_critical_anomalies(dest_channel, dest_url)
                st.success(f"✓ Successfully dispatched **{len(dispatched)}** CRITICAL anomaly alert payloads to {dest_channel}!")
                st.json(dispatched[0]["payload"])

        # Alert History Audit Trail
        st.markdown("##### 📜 Recent Alert Dispatch Audit Trail")
        simulator = AlertSimulator()
        logs = simulator.get_alert_history(limit=10)
        if logs:
            st.dataframe(pd.DataFrame(logs), use_container_width=True)

    st.markdown("---")

    # Filters
    fcol1, fcol2 = st.columns(2)
    with fcol1:
        sev_filter = st.multiselect("Filter Severity", ["CRITICAL", "HIGH", "MEDIUM"], default=["CRITICAL", "HIGH", "MEDIUM"])
    with fcol2:
        type_filter = st.multiselect(
            "Filter Anomaly Type",
            ["Resolution Time Outlier", "SLA Breach", "Response Time Spike", "Customer Dissatisfaction Anomaly"],
            default=["Resolution Time Outlier", "SLA Breach", "Response Time Spike", "Customer Dissatisfaction Anomaly"]
        )

    filtered_anomalies = [
        a for a in report["anomalies"]
        if a["severity"] in sev_filter and a["anomaly_type"] in type_filter
    ]

    st.markdown(f"### 🚩 Flagged Ticket Diagnostics ({len(filtered_anomalies)} items)")

    for item in filtered_anomalies:
        badge_class = "badge-critical" if item["severity"] == "CRITICAL" else "badge-high" if item["severity"] == "HIGH" else "badge-medium"
        
        with st.expander(f"📌 [{item['ticket_id']}] {item['anomaly_type']} - Priority: {item['priority']} | Status: {item['status']}", expanded=(item["severity"] == "CRITICAL")):
            st.markdown(f"<span class='{badge_class}'>{item['severity']} SEVERITY</span>", unsafe_allow_html=True)
            st.markdown(f"**Issue Summary:** {item['issue_summary']}")
            st.markdown(f"**Category:** {item['category']} | **Assigned Agent:** {item['agent_id']}")
            st.markdown("**Diagnostic Findings:**")
            for r in item["reasons"]:
                st.markdown(f"- ⚠️ {r}")

# ==========================================
# TAB 4: TICKET EXPLORER
# ==========================================
elif navigation == "🔍 Ticket Explorer":
    st.markdown("""
    <div class="header-card">
        <h1>🔍 Support Ticket Data Explorer</h1>
        <p style="color: #8b949e; margin-bottom: 0;">Search, filter, and inspect raw support ticket records.</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st_cat = st.selectbox("Category", ["All", "Billing", "Technical", "General"])
    with col2:
        st_prio = st.selectbox("Priority", ["All", "Low", "Medium", "High", "Critical"])
    with col3:
        st_stat = st.selectbox("Status", ["All", "Open", "Resolved", "Escalated"])

    where_clauses = []
    if st_cat != "All":
        where_clauses.append(f"category = '{st_cat}'")
    if st_prio != "All":
        where_clauses.append(f"priority = '{st_prio}'")
    if st_stat != "All":
        where_clauses.append(f"status = '{st_stat}'")

    where_str = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    sql_exp = f"SELECT * FROM tickets{where_str} ORDER BY ticket_id ASC"

    tickets_res = execute_query(sql_exp)
    if tickets_res["success"]:
        df_tickets = pd.DataFrame(tickets_res["rows"])
        st.markdown(f"Showing **{len(df_tickets)}** ticket records:")
        st.dataframe(df_tickets, use_container_width=True)

        # Download CSV
        csv_data = df_tickets.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download Filtered CSV Data",
            data=csv_data,
            file_name="filtered_tickets.csv",
            mime="text/csv"
        )

# ==========================================
# TAB 5: VIDEO TUTORIAL & USER GUIDE
# ==========================================
elif navigation == "🎥 Video Tutorial & User Guide":
    if os.path.exists(TUTORIAL_BANNER):
        st.image(TUTORIAL_BANNER, use_container_width=True)

    st.markdown("""
    <div class="header-card">
        <h1>🎥 Instruction Guide & Video Tutorial Hub</h1>
        <p style="color: #8b949e; margin-bottom: 0;">Learn how to navigate the platform, query ticket data using natural language AI, diagnose operational anomalies, and trigger automated alerts step-by-step.</p>
    </div>
    """, unsafe_allow_html=True)

    # Interactive Demo Walkthrough Scenarios
    st.subheader("🎬 Interactive Video Walkthrough & Feature Demos")
    st.write("Click any demo scenario below to trigger a live interactive tutorial walkthrough:")

    dcol1, dcol2, dcol3 = st.columns(3)
    
    with dcol1:
        if st.button("▶️ Demo 1: Unresolved Critical Tickets", use_container_width=True):
            st.info("⚡ **Running Scenario 1:** Querying unresolved Critical tickets...")
            engine = QueryEngine()
            res = engine.process_query("How many critical tickets are unresolved?")
            st.success(f"**AI Answer:** {res['answer_summary']}")
            st.code(res['sql'], language='sql')

    with dcol2:
        if st.button("▶️ Demo 2: Lowest Rating Agent", use_container_width=True):
            st.info("⚡ **Running Scenario 2:** Identifying agent performance metrics...")
            engine = QueryEngine()
            res = engine.process_query("Which agent has the lowest average customer rating?")
            st.success(f"**AI Answer:** {res['answer_summary']}")
            st.code(res['sql'], language='sql')

    with dcol3:
        if st.button("▶️ Demo 3: Anomaly & Alert Dispatch", use_container_width=True):
            st.info("⚡ **Running Scenario 3:** Running anomaly detection and triggering Webhook notification...")
            simulator = AlertSimulator()
            dispatched = simulator.dispatch_all_critical_anomalies()
            st.success(f"**Alert Engine Output:** Dispatched {len(dispatched)} CRITICAL alert payloads via Webhook.")
            st.json(dispatched[0]["payload"])

    st.markdown("---")

    # Step-by-Step How To Guide
    st.subheader("📖 Step-by-Step User Identification & Operation Guide")

    st.markdown("""
    <div class="step-box">
        <div class="step-title">Step 1: Monitor Executive KPIs & Team Performance</div>
        <p>Go to the <b>📊 Executive Dashboard</b> tab to review total tickets, open/resolved ratios, average resolution time, and customer satisfaction ratings. Filter agent performance to identify high-performing agents or bottlenecks.</p>
    </div>
    
    <div class="step-box">
        <div class="step-title">Step 2: Ask Plain English Questions to the AI</div>
        <p>Switch to the <b>💬 Natural Language Query</b> tab. Type questions such as <i>"How many tickets are currently open?"</i> or click one of the pre-built sample buttons. The AI system will convert your question into SQL, execute it, display tabular results, and plot automated charts.</p>
    </div>
    
    <div class="step-box">
        <div class="step-title">Step 3: Diagnose Operational Anomalies & Trigger Webhook Alerts</div>
        <p>Open the <b>🚨 Anomaly Hub</b> tab to view automatically flagged tickets. Filter by severity (<code>CRITICAL</code>, <code>HIGH</code>, <code>MEDIUM</code>) or anomaly type. Expand the <b>🔔 Automated Alert & Notification Center</b> to trigger live Webhook alert dispatches to Slack, Microsoft Teams, or PagerDuty.</p>
    </div>
    
    <div class="step-box">
        <div class="step-title">Step 4: Explore Raw Data & Export Reports</div>
        <p>Use the <b>🔍 Ticket Explorer</b> tab to filter raw support tickets by Category, Priority, or Status, and click <b>📥 Download Filtered CSV Data</b> to export custom datasets for offline reporting.</p>
    </div>
    """, unsafe_allow_html=True)
