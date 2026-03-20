import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import httpx
from azure.cosmos import CosmosClient
import os
from dotenv import load_dotenv
 
load_dotenv()
 
# PAGE CONFIG
 
st.set_page_config(
    page_title="DevGuard AI Gateway",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)
 
#  UI STYLE
 
st.markdown("""
<style>
 
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Space+Mono:wght@400;700&display=swap%27);
 
.stApp {
background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 100%);
}
 
h1,h2,h3 {
font-family: 'Orbitron', sans-serif !important;
background: linear-gradient(135deg, #00ff88, #00ccff);
-webkit-background-clip: text;
-webkit-text-fill-color: transparent;
font-weight: 900;
letter-spacing: 2px;
}
 
.status-dot{
display:inline-block;
width:10px;
height:10px;
background:#00ff88;
border-radius:50%;
animation:pulse 2s infinite;
margin-right:8px;
}
 
@keyframes pulse{
0%,100%{opacity:1}
50%{opacity:0.4}
}
 
</style>
""", unsafe_allow_html=True)
 
# COSMOS DB CONNECTION
 
@st.cache_resource
def get_cosmos_container():
 
    try:
 
        COSMOS_URI = os.getenv("COSMOS_URI")
        COSMOS_KEY = os.getenv("COSMOS_KEY")
 
        if not COSMOS_URI or not COSMOS_KEY:
            st.error("Cosmos DB credentials missing")
            return None
 
        client = CosmosClient(COSMOS_URI, credential=COSMOS_KEY)
 
        database = client.get_database_client("devguard")
 
        container = database.get_container_client("audit_logs")
 
        return container
 
    except Exception as e:
 
        st.error(f"Cosmos DB connection failed: {e}")
        return None
 
 
@st.cache_data(ttl=10)
def fetch_audit_logs():
 
    container = get_cosmos_container()
 
    if not container:
        return []
 
    try:
 
        query = "SELECT * FROM c ORDER BY c._ts DESC OFFSET 0 LIMIT 100"
 
        items = list(container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
 
        return items
 
    except Exception as e:
 
        st.error(f"Error fetching logs: {e}")
        return []
 
# HEADER
 
col1, col2 = st.columns([3,1])
 
with col1:
 
    st.markdown("# 🛡️ DEV-GUARD AI GATEWAY")
    st.markdown("### Agentic Governance Dashboard")
 
with col2:
 
    st.markdown(
    '<div style="text-align:right;padding-top:20px;">'
    '<span class="status-dot"></span>'
    '<span style="color:#00ff88;font-weight:700;">SYSTEM ACTIVE</span>'
    '</div>',
    unsafe_allow_html=True
    )
 
if st.button("🔄 REFRESH"):
    st.cache_data.clear()
    st.rerun()
 
st.markdown("---")
 
# =====================================================
# FETCH DATA
# ======================================================
 
with st.spinner("Loading logs..."):
 
    audit_logs = fetch_audit_logs()
 
# ======================================================
# CALCULATE STATS
# ======================================================
 
total_requests = len(audit_logs)
 
allowed_requests = sum(
    1 for log in audit_logs if log.get("allowed", False)
)
 
blocked_requests = total_requests - allowed_requests
 
total_cost = sum(
    log.get("cost_usd") or 0 for log in audit_logs
)

# METRICS
 
col1,col2,col3,col4 = st.columns(4)
 
with col1:
    st.metric("Total Requests", total_requests)
 
with col2:
    st.metric("Allowed", allowed_requests)
 
with col3:
    st.metric("Blocked", blocked_requests)
 
with col4:
    st.metric("Total Cost", f"${total_cost:.4f}")
 
st.markdown("---")
 
# ======================================================
# REQUEST STATUS PIE CHART
# ======================================================
 
col1,col2 = st.columns(2)
 
with col1:
 
    st.markdown("### Request Status")
 
    if total_requests > 0:
 
        fig = go.Figure(
        data=[
            go.Pie(
                labels=["Allowed","Blocked"],
                values=[allowed_requests,blocked_requests],
                hole=0.4
            )
        ])
 
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            height=350
        )
 
        st.plotly_chart(fig, width="stretch")
 
    else:
 
        st.info("No requests yet")
 
# ======================================================
# VIOLATION CHART
# ======================================================
 
with col2:
 
    st.markdown("### Violations")
 
    violations=[]
 
    for log in audit_logs:
 
        if not log.get("allowed",True):
            violations.extend(log.get("violations",[]))
 
    if violations:
 
        from collections import Counter
 
        counts=Counter(violations)
 
        fig=go.Figure(
        data=[
            go.Bar(
                x=list(counts.values()),
                y=list(counts.keys()),
                orientation="h"
            )
        ])
 
        st.plotly_chart(fig, width="stretch")
 
    else:
 
        st.info("No violations detected")
 
st.markdown("---")
 
# ======================================================
# AUDIT LOG TABLE
# ======================================================
 
st.markdown("### Recent Audit Logs")
 
if audit_logs:
 
    df=pd.DataFrame(audit_logs)
 
    cols=[
        "timestamp",
        "project_id",
        "allowed",
        "violations",
        "tokens_used_request",
        "cost_usd"
    ]
 
    cols=[c for c in cols if c in df.columns]
 
    df=df[cols].head(20)
 
    if "allowed" in df.columns:
        df["allowed"]=df["allowed"].apply(
            lambda x:"✅ Allowed" if x else "❌ Blocked"
        )
 
    if "violations" in df.columns:
        df["violations"]=df["violations"].apply(
            lambda x:", ".join(x) if x else "-"
        )
 
    st.dataframe(df, width="stretch")
 
else:
 
    st.info("No logs yet")
 
# ======================================================
# TEST API
# ======================================================
 
st.markdown("---")
st.markdown("### Test DevGuard API")
 
project_id=st.text_input("Project ID","demo_project")
 
prompt=st.text_area(
"Prompt",
"Explain quantum computing simply"
)
 
if st.button("Send Request"):
 
    try:
 
        response=httpx.post(
        "http://localhost:8000/generate",
        json={
            "project_id":project_id,
            "prompt":prompt
        },
        timeout=30
        )
 
        if response.status_code==200:
 
            st.success("Request success")
 
            st.json(response.json())
 
        else:
 
            st.error(response.text)
 
    except Exception as e:
 
        st.error(f"Connection error: {e}")
 
# ======================================================
# SIDEBAR
# ======================================================
 
with st.sidebar:
 
    st.markdown("## Dev-Guard")
 
    st.markdown("""
AI Governance Layer
 
• Prompt Security  
• Token Monitoring  
• Cost Tracking  
• Violation Detection
""")
 
    st.markdown("---")
 
    st.markdown("### API")
 
    st.code("POST /devguard/run")
 
    st.markdown("Swagger: http://localhost:8000/docs")
 
# ======================================================
# FOOTER
# ======================================================
 
st.markdown("---")
 
st.markdown(
f"<div style='text-align:center;color:gray'>Dev-Guard Dashboard | {datetime.now().date()}</div>",
unsafe_allow_html=True
)