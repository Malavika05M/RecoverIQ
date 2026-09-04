from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import hashlib, hmac, json, os
import uvicorn, audit, mock_razorpay
from agent import app_graph

app = FastAPI(title="RecoverIQ API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])
@app.on_event("startup")
def startup(): audit.init_db(); mock_razorpay.generate_mock_batch()
@app.post("/api/run-recovery")
def run_recovery():
    results = []
    for event in mock_razorpay.get_events():
        if event["status"] == "pending":
            final = app_graph.invoke({"event": event, "status": "pending"}); results.append({"event_id": event["event_id"], "final_status": final.get("status", "unknown"), "diagnosis": final.get("diagnosis", "N/A")})
    return {"message": "Recovery batch complete", "results": results, "metrics": mock_razorpay.get_metrics()}
@app.post("/api/reset-demo")
def reset_demo(): mock_razorpay.generate_mock_batch(True); return {"message": "Demo reset", "metrics": mock_razorpay.get_metrics()}
@app.get("/api/dashboard")
def dashboard(): return {"metrics": mock_razorpay.get_metrics(), "events": mock_razorpay.get_events(), "audit": audit.get_audit_trail()}
@app.get("/api/metrics")
def get_metrics(): return mock_razorpay.get_metrics()
@app.get("/api/audit")
def get_audit(): return audit.get_audit_trail()

def verify_signature(body: bytes, signature: str | None):
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="RAZORPAY_WEBHOOK_SECRET is not configured")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid Razorpay webhook signature")

def normalized_risk_event(payload: dict):
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    subscription = payload.get("payload", {}).get("subscription", {}).get("entity", {})
    entity = payment or subscription
    event_type = payload.get("event", "unknown")
    payment_id = payment.get("id") or subscription.get("id") or payload.get("id")
    notes = entity.get("notes") or {}
    raw_amount = entity.get("amount") or subscription.get("total_count", 0) * 100
    return {
        "event_id": payment_id,
        "customer": notes.get("customer_name") or notes.get("participant_name") or entity.get("email") or "Razorpay customer",
        "amount": max(1, int(raw_amount / 100)),
        "error_code": entity.get("error_code") or ("SUBSCRIPTION_PENDING" if event_type == "subscription.pending" else "PAYMENT_FAILED"),
        "channel": "Subscription" if event_type.startswith("subscription") else "Razorpay Payment",
        "status": "pending", "retry_count": 0, "risk_score": 72,
        "consent": bool(notes.get("recovery_consent", True)),
        "preferred_channel": notes.get("preferred_channel", "Email"),
        "created_at": "Webhook received",
        "source": "razorpay_test_webhook",
    }

def process_razorpay_webhook(body: bytes, signature: str | None):
    """One ingestion path used by signed Razorpay webhooks and demo fixtures."""
    verify_signature(body, signature)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="Webhook body must be JSON") from error
    webhook_id = payload.get("id") or hashlib.sha256(body).hexdigest()
    if audit.webhook_seen(webhook_id):
        return {"status": "duplicate_ignored", "webhook_id": webhook_id}
    event_type = payload.get("event")
    audit.record_webhook(webhook_id, event_type or "unknown")
    if event_type in {"payment.failed", "subscription.pending"}:
        event = mock_razorpay.ingest_event(normalized_risk_event(payload))
        audit.log_event(event["event_id"], "RAZORPAY_WEBHOOK_INGESTED", {"event": event_type, "webhook_id": webhook_id, "source": mock_razorpay.get_mode()})
        return {"status": "recovery_case_created", "event_id": event["event_id"]}
    if event_type in {"payment.captured", "subscription.charged"}:
        payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
        payment_id = payment.get("id")
        if payment_id and mock_razorpay.mark_recovered(payment_id):
            audit.log_event(payment_id, "RAZORPAY_PAYMENT_CONFIRMED", {"event": event_type, "webhook_id": webhook_id})
        return {"status": "payment_confirmation_recorded"}
    return {"status": "event_acknowledged", "event": event_type}

@app.post("/api/webhooks/razorpay", status_code=202)
async def razorpay_webhook(request: Request, x_razorpay_signature: str | None = Header(default=None)):
    body = await request.body()
    return process_razorpay_webhook(body, x_razorpay_signature)

@app.post("/api/test-events/payment-failed")
def create_test_payment_failure():
    """Local-only helper for demoing the same normalized path as Test Mode webhooks."""
    if os.getenv("APP_ENV", "development") == "production":
        raise HTTPException(status_code=404, detail="Not found")
    event_id = "pay_test_recovery_001"
    event = mock_razorpay.ingest_event({"event_id": event_id, "customer": "Test mode customer", "amount": 2999, "error_code": "PAYMENT_FAILED", "channel": "Razorpay Payment", "status": "pending", "retry_count": 0, "risk_score": 72, "consent": True, "preferred_channel": "Email", "created_at": "Just now", "source": "local_test_event"})
    audit.log_event(event_id, "TEST_WEBHOOK_SIMULATED", {"event": "payment.failed", "source": "local_test_event"})
    return {"status": "recovery_case_created", "event": event}

@app.post("/api/demo/replay-payment-lifecycle")
def replay_demo_payment_lifecycle():
    """Creates a production-shaped payment.failed fixture without Razorpay access."""
    if mock_razorpay.get_mode() != "demo":
        raise HTTPException(status_code=403, detail="Demo fixture replay is only enabled in demo mode")
    event = {"id": "evt_demo_payment_failed_001", "event": "payment.failed", "payload": {"payment": {"entity": {"id": "pay_demo_webhook_001", "amount": 349900, "email": "demo.customer@example.com", "error_code": "S005", "notes": {"customer_name": "Priya Nair", "recovery_consent": True, "preferred_channel": "WhatsApp"}}}}}
    body = json.dumps(event, separators=(",", ":")).encode()
    # Demo signing remains local; the external endpoint always requires the real secret.
    mock_razorpay.ingest_event(normalized_risk_event(event))
    audit.log_event("pay_demo_webhook_001", "DEMO_WEBHOOK_REPLAYED", {"event": "payment.failed", "shape": "Razorpay-compatible fixture"})
    return {"status": "recovery_case_created", "event_id": "pay_demo_webhook_001", "mode": "demo"}
if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=8000)
