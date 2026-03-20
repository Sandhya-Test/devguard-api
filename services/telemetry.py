# services/telemetry.py
#
# Azure App Insights telemetry.
#
# BUG FIX: AzureLogHandler was recreated on every request,
# opening a new aiohttp session each time and never closing it.
# Fix: Handler created ONCE as a module-level singleton.
# export_interval=0 forces synchronous flush — no background thread.
 
import os
import logging
from dotenv import load_dotenv
 
load_dotenv()
 
connection_string = os.getenv("APPINSIGHTS_CONNECTION_STRING")
 
# ── Logger ──
logger = logging.getLogger("devguard-metrics")
logger.setLevel(logging.INFO)
 
# ── Singleton handler — one session for the entire app lifetime ──
_handler = None
 
if connection_string:
    try:
        from opencensus.ext.azure.log_exporter import AzureLogHandler
        _handler = AzureLogHandler(connection_string=connection_string)
        _handler.export_interval = 0   # flush immediately, no background thread
        logger.addHandler(_handler)
        print("[Telemetry] Azure App Insights connected.")
    except Exception as e:
        print(f"[Telemetry] App Insights setup failed (non-fatal): {e}")
else:
    print("[Telemetry] APPINSIGHTS_CONNECTION_STRING not set — telemetry disabled.")
 
 
# ── Telemetry functions ──
 
def track_request(project_id: str):
    logger.info(
        "devguard_request",
        extra={"custom_dimensions": {"project_id": project_id}}
    )
 
 
def track_blocked(project_id: str, reason: str):
    logger.warning(
        "devguard_blocked",
        extra={"custom_dimensions": {
            "project_id": project_id,
            "reason":     reason,
        }}
    )
 
 
def track_cost(project_id: str, cost: float):
    logger.info(
        "devguard_cost",
        extra={"custom_dimensions": {
            "project_id": project_id,
            "cost_usd":   str(cost),
        }}
    )
 
 
def track_latency(project_id: str, latency: float):
    logger.info(
        "devguard_latency",
        extra={"custom_dimensions": {
            "project_id": project_id,
            "latency_ms": str(latency),
        }}
    )
 
 
def flush():
    """Call on app shutdown to close the aiohttp session cleanly."""
    if _handler:
        try:
            _handler.flush()
        except Exception:
            pass