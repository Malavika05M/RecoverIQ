"""In-memory Razorpay-style recovery data used by the hackathon demo."""
from copy import deepcopy
import os

AT_RISK_REVENUE = []
SEED_BATCH = [
    {"event_id": "pay_8F2A", "customer": "Ananya Sharma", "amount": 5000, "error_code": "S005", "channel": "UPI AutoPay", "status": "pending", "retry_count": 0, "risk_score": 91, "consent": True, "preferred_channel": "WhatsApp", "created_at": "Today, 09:42"},
    {"event_id": "sub_9K7D", "customer": "Rohan Mehta", "amount": 1500, "error_code": "S008", "channel": "UPI AutoPay", "status": "pending", "retry_count": 1, "risk_score": 84, "consent": True, "preferred_channel": "SMS", "created_at": "Today, 10:15"},
    {"event_id": "inv_1C4P", "customer": "Banyan Works Pvt Ltd", "amount": 12000, "error_code": "B2B_OVERDUE", "channel": "Invoice", "status": "pending", "retry_count": 2, "risk_score": 76, "consent": True, "preferred_channel": "Voice", "created_at": "Yesterday"},
    {"event_id": "chk_4R9L", "customer": "Kavya Iyer", "amount": 2499, "error_code": "CHECKOUT_ABANDONED", "channel": "Checkout", "status": "pending", "retry_count": 0, "risk_score": 68, "consent": True, "preferred_channel": "WhatsApp", "created_at": "Today, 11:03"},
    {"event_id": "pay_2M8Q", "customer": "Farhan Khan", "amount": 899, "error_code": "S005", "channel": "UPI AutoPay", "status": "pending", "retry_count": 0, "risk_score": 59, "consent": False, "preferred_channel": "SMS", "created_at": "Today, 11:28"},
]

def generate_mock_batch(reset=True):
    global AT_RISK_REVENUE
    if reset or not AT_RISK_REVENUE:
        AT_RISK_REVENUE = deepcopy(SEED_BATCH)
    return AT_RISK_REVENUE

def get_events(): return AT_RISK_REVENUE
def get_mode(): return os.getenv("RAZORPAY_MODE", "demo").lower()
def find_event(event_id): return next((e for e in AT_RISK_REVENUE if e["event_id"] == event_id), None)
def update_event(event_id, **values):
    event = find_event(event_id)
    if event: event.update(values)
    return event
def schedule_retry(event_id, retry_date):
    event = find_event(event_id)
    if event:
        event["scheduled_retry"] = retry_date
        event["retry_count"] += 1
        event["status"] = "scheduled"
    return bool(event)
def mark_recovered(event_id): return bool(update_event(event_id, status="recovered"))
def ingest_event(event):
    """Store a normalized event from the Razorpay webhook adapter."""
    if find_event(event["event_id"]):
        return find_event(event["event_id"])
    AT_RISK_REVENUE.append(event)
    return event
def get_metrics():
    events = AT_RISK_REVENUE
    total = sum(e["amount"] for e in events)
    recovered = sum(e["amount"] for e in events if e["status"] == "recovered")
    return {"total_at_risk": total, "recovered": recovered, "active_cases": sum(1 for e in events if e["status"] in {"pending", "scheduled"}), "protected_cases": sum(1 for e in events if e["status"] == "human_review"), "recovery_rate": round(recovered / total * 100, 1) if total else 0, "mode": get_mode()}
