from typing import TypedDict, Dict, Any
from langgraph.graph import StateGraph, END
import audit
import mock_razorpay

class AgentState(TypedDict, total=False):
    event: Dict[str, Any]; diagnosis: str; intervention: str; compliance_passed: bool; voice_transcript: str; p2p_date: str; status: str

PLAYBOOKS = {
    "S005": ("Insufficient balance", "Retry after the customer’s salary window"),
    "S008": ("UPI mandate revoked", "Send a secure mandate re-authentication link"),
    "B2B_OVERDUE": ("Invoice overdue", "Route to a consented collections specialist"),
    "CHECKOUT_ABANDONED": ("Checkout abandoned", "Send a one-tap, expiry-bound payment link"),
}
def triage_node(state):
    e = state["event"]; audit.log_event(e["event_id"], "TRIAGE", {"amount": e["amount"], "channel": e["channel"], "risk_score": e["risk_score"]}); return {"status": "triaged"}
def diagnose_node(state):
    e = state["event"]; diagnosis, intervention = PLAYBOOKS.get(e["error_code"], ("Unknown payment issue", "Escalate for review")); audit.log_event(e["event_id"], "ROOT_CAUSE_CLASSIFIED", {"root_cause": diagnosis, "recommended_action": intervention}); return {"diagnosis": diagnosis, "intervention": intervention}
def compliance_node(state):
    e = state["event"]
    if not e.get("consent"):
        audit.log_event(e["event_id"], "COMPLIANCE_BLOCK", {"reason": "No contact consent on record"}); mock_razorpay.update_event(e["event_id"], status="human_review", decision="Consent required", guardrail="Contact suppressed"); return {"compliance_passed": False, "status": "human_review"}
    if e["retry_count"] >= 2:
        audit.log_event(e["event_id"], "STOPPING_RULE_TRIGGERED", {"reason": "Maximum two automated retries reached"}); mock_razorpay.update_event(e["event_id"], status="human_review", decision="Human review", guardrail="Retry limit reached"); return {"compliance_passed": False, "status": "human_review"}
    audit.log_event(e["event_id"], "POLICY_GATE_PASSED", {"consent": True, "retry_count": e["retry_count"], "quiet_hours": "Respected"}); return {"compliance_passed": True}
def execute_node(state):
    e = state["event"]
    transcript = "Secure UPI mandate re-authentication link delivered by SMS." if e["error_code"] == "S008" else "One-tap payment link delivered on WhatsApp; link expires in 30 minutes." if e["error_code"] == "CHECKOUT_ABANDONED" else f"Namaskar {e['customer']}, aapka ₹{e['amount']:,} payment pending hai. Customer promised payment after the next salary cycle."
    audit.log_event(e["event_id"], "BOUNDED_INTERVENTION_EXECUTED", {"channel": e["preferred_channel"], "message": transcript}); return {"voice_transcript": transcript}
def extract_p2p_node(state):
    e = state["event"]; date = "2026-09-10" if e["error_code"] == "S005" else "immediate"; audit.log_event(e["event_id"], "COMMITMENT_CAPTURED", {"commitment": date, "confidence": "high"}); return {"p2p_date": date}
def action_node(state):
    e = state["event"]; commitment = state["p2p_date"]; mock_razorpay.schedule_retry(e["event_id"], commitment); mock_razorpay.update_event(e["event_id"], decision=state["intervention"], guardrail="Consent + retry policy passed")
    # Demo mode closes the loop with a simulated provider callback. Test/Live must
    # wait for a real captured/charged webhook before revenue is counted.
    if mock_razorpay.get_mode() == "demo":
        mock_razorpay.mark_recovered(e["event_id"]); audit.log_event(e["event_id"], "DEMO_PAYMENT_CONFIRMED", {"amount": e["amount"], "commitment": commitment, "provider": "Razorpay demo adapter"}); return {"status": "recovered"}
    audit.log_event(e["event_id"], "RECOVERY_ACTION_SCHEDULED", {"amount": e["amount"], "commitment": commitment, "awaiting": "Razorpay payment confirmation webhook"}); return {"status": "scheduled"}

workflow = StateGraph(AgentState)
for name, node in [("triage", triage_node), ("diagnose", diagnose_node), ("compliance", compliance_node), ("execute", execute_node), ("extract_p2p", extract_p2p_node), ("action", action_node)]: workflow.add_node(name, node)
workflow.set_entry_point("triage"); workflow.add_edge("triage", "diagnose"); workflow.add_edge("diagnose", "compliance"); workflow.add_conditional_edges("compliance", lambda state: "execute" if state["compliance_passed"] else END); workflow.add_edge("execute", "extract_p2p"); workflow.add_edge("extract_p2p", "action"); app_graph = workflow.compile()
