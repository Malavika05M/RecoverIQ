# RecoverIQ — AI Revenue Recovery

RecoverIQ is a bounded revenue-recovery operations platform built for **Razorpay Hackathon Track 03: AI Revenue Recovery**. It turns payment-risk signals into an appropriate, policy-checked next action—and makes every decision understandable and auditable.

It is designed for payment failures, mandate problems, abandoned checkouts, and overdue receivables. Rather than merely listing failures, RecoverIQ decides whether to recover, wait, or stop and escalate.

## The problem

Revenue rarely disappears in one event. A payment may fail due to insufficient balance, a mandate may be revoked, a customer may abandon checkout, or an invoice may become overdue. Teams often identify these problems but still rely on fragmented, manual follow-up.

RecoverIQ answers:

- Which revenue is at risk?
- Why did it happen?
- What is the safest next action?
- Should automation stop and a human take over?
- Was money actually recovered, or was an action merely attempted?

## What RecoverIQ does

1. Ingests a risk event from a Razorpay-compatible payment or subscription event.
2. Classifies the root cause and chooses only from approved recovery playbooks.
3. Applies deterministic guardrails before outreach or retries.
4. Executes a bounded intervention, such as a salary-window retry, re-authentication link, payment link, or human follow-up.
5. Tracks the outcome and writes a hash-chained audit record.
6. Counts recovery correctly: Test and Live modes only count recovered revenue after a payment-confirmation webhook.

## Supported recovery playbooks

| Signal | Approved action | Boundary |
| --- | --- | --- |
| Insufficient balance | Retry after an approved salary window | No rapid or repeated retrying |
| Revoked UPI mandate | Send secure mandate re-authentication flow | Never request sensitive payment credentials |
| Checkout abandoned | Send a short-lived payment link | One bounded reminder |
| B2B invoice overdue | Prepare a concise follow-up for an owner | High-friction cases go to human review |

## Guardrails

- **Contact consent:** no recorded consent means no automated outreach.
- **Two-retry ceiling:** automation stops after two attempts.
- **Human review:** cases that fail a policy check are protected and routed for review.
- **Verified outcomes:** scheduled actions are not counted as recovered money.
- **Auditability:** triage, diagnosis, policy decisions, actions, and confirmations are hash-chained in the audit ledger.

## Demo Mode — no Razorpay account required

RecoverIQ defaults to credential-free **Demo Mode**. Its initial queue contains clearly labelled, locally seeded sandbox cases; this is not live Razorpay or customer data.

To demonstrate the webhook lifecycle:

1. Open **Controls** in the UI.
2. Select **Replay payment failure webhook**.
3. RecoverIQ creates a case from a Razorpay-shaped payment.failed fixture.
4. Open the case to see what happened, the selected action, what the customer would experience, and the applicable guardrail.
5. Run the recovery batch and inspect the audit ledger.

Demo Mode simulates provider confirmation so a complete recovery story can be shown without sending money or contacting a person.

## Test and Live Mode behavior

The same application is ready to use signed Razorpay webhooks when credentials are available.

| Mode | Risk-event source | Recovery confirmation |
| --- | --- | --- |
| demo (default) | Local fixtures and local webhook replay | Demo adapter simulation |
| test | Razorpay Test Mode webhooks | Actual Test Mode confirmation webhook |
| live | Razorpay Live Mode webhooks | Actual Live Mode confirmation webhook |

In Test and Live modes, RecoverIQ schedules an approved action but does **not** mark money recovered until a payment.captured or subscription.charged event confirms it.

## Razorpay webhook integration

Webhook receiver:

~~~text
POST /api/webhooks/razorpay
~~~

It validates the raw webhook body using the X-Razorpay-Signature HMAC SHA-256 signature, records webhook IDs for idempotency, and accepts:

- payment.failed
- payment.captured
- subscription.pending
- subscription.charged

When you obtain Razorpay Test Mode access:

~~~bash
export RAZORPAY_MODE="test"
export RAZORPAY_WEBHOOK_SECRET="your-test-mode-webhook-secret"
~~~

Configure Razorpay Test Mode to send events to:

~~~text
https://your-domain.example/api/webhooks/razorpay
~~~

Never place a live secret in source control.

## Architecture

~~~text
Razorpay-shaped event / Razorpay webhook
                ↓
       Signature + duplicate check
                ↓
       Normalize into recovery case
                ↓
  Diagnose → policy gate → approved playbook
                ↓
    Scheduled action / human review
                ↓
  Razorpay confirmation → recovered revenue
                ↓
       Hash-chained audit ledger
~~~

### Key components

- backend/main.py — FastAPI APIs, mode handling, webhook verification and ingestion.
- backend/agent.py — LangGraph recovery workflow and policy routing.
- backend/mock_razorpay.py — Demo provider adapter and normalized case store.
- backend/audit.py — SQLite-backed audit trail and webhook de-duplication.
- frontend/ui/app/page.tsx — Recovery workspace, case explainer, playbooks, controls, and audit UI.

## Run locally

Start the backend:

~~~bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
~~~

Start the frontend in another terminal:

~~~bash
cd frontend/ui
npm install
npm run dev
~~~

Open [http://localhost:3000](http://localhost:3000).

## Current scope and production path

The current project demonstrates recovery decisioning, safety, measurement, and webhook-integration shape with an in-memory Demo Mode adapter. A production deployment should replace that adapter with durable storage and verified Razorpay integration; persist customer consent and contact preferences; queue recovery commands; use provider/payment IDs as idempotency keys; and keep the policy gate deterministic and independently auditable.
