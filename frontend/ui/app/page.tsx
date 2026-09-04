"use client";

import { useEffect, useState } from "react";
import Image from "next/image";

const API = "http://localhost:8000/api";
type View = "command" | "queue" | "playbooks" | "ledger" | "settings";
type Metrics = { total_at_risk: number; recovered: number; active_cases: number; protected_cases: number; recovery_rate: number };
type RecoveryCase = { event_id: string; customer: string; amount: number; error_code: string; channel: string; status: string; risk_score: number; preferred_channel: string; created_at: string; decision?: string; guardrail?: string };
type Audit = [string, string, string, string, string];

const emptyMetrics: Metrics = { total_at_risk: 0, recovered: 0, active_cases: 0, protected_cases: 0, recovery_rate: 0 };
const money = (value: number) => `₹${value.toLocaleString("en-IN")}`;
const title: Record<View, [string, string]> = {
  command: ["Recovery command center", "See where revenue is at risk and what RecoverIQ is doing about it."],
  queue: ["Recovery queue", "Every account has a clear owner, reason, next action, and stopping rule."],
  playbooks: ["Recovery playbooks", "Approved interventions only. AI chooses between them; it does not invent collection tactics."],
  ledger: ["Audit ledger", "A tamper-evident record of every decision and action."],
  settings: ["Recovery controls", "Set the operating boundaries your team is comfortable with."],
};

export default function Home() {
  const [view, setView] = useState<View>("command");
  const [metrics, setMetrics] = useState<Metrics>(emptyMetrics);
  const [events, setEvents] = useState<RecoveryCase[]>([]);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [running, setRunning] = useState(false);
  const [notice, setNotice] = useState("Sandbox data loaded. You can safely run the complete recovery flow.");
  const [selected, setSelected] = useState<RecoveryCase | null>(null);
  const [autopilot, setAutopilot] = useState(true);

  const refresh = async () => {
    try {
      const data = await (await fetch(`${API}/dashboard`)).json();
      setMetrics(data.metrics);
      setEvents(data.events);
      setAudit(data.audit);
    } catch {
      setNotice("Backend unavailable — start FastAPI on port 8000 to connect the live queue.");
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => { refresh(); }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const runRecovery = async () => {
    setRunning(true);
    setNotice("Working through the queue: classify → verify policy → contact or stop → record outcome.");
    try {
      const data = await (await fetch(`${API}/run-recovery`, { method: "POST" })).json();
      await refresh();
      setNotice(`${data.results.length} cases completed. ${money(data.metrics.recovered)} is confirmed recovered; protected cases were not contacted.`);
    } catch {
      setNotice("Couldn’t run the batch. Confirm that the backend is running on port 8000.");
    } finally {
      setRunning(false);
    }
  };

  const resetDemo = async () => {
    await fetch(`${API}/reset-demo`, { method: "POST" });
    await refresh();
    setNotice("Demo queue reset. No customer was contacted — this is sandbox data.");
  };
  const replayDemoWebhook = async () => {
    try {
      await fetch(`${API}/demo/replay-payment-lifecycle`, { method: "POST" });
      await refresh();
      setNotice("Razorpay-shaped demo webhook replayed. It is now in the queue, using the same event normalization as Test Mode.");
      setView("queue");
    } catch {
      setNotice("Couldn’t create the test event. Confirm that the backend is running.");
    }
  };

  const heading = title[view];
  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><Image src="/brand/recoveriq-mark.png" alt="RecoverIQ logo" width={48} height={48} priority /></div><div>Recover<span>IQ</span><small>REVENUE OPERATIONS</small></div></div>
        <nav>
          <Nav label="Command center" icon="⌘" active={view === "command"} onClick={() => setView("command")} />
          <Nav label="Recovery queue" icon="◉" badge={metrics.active_cases} active={view === "queue"} onClick={() => setView("queue")} />
          <Nav label="Playbooks" icon="◫" active={view === "playbooks"} onClick={() => setView("playbooks")} />
          <Nav label="Audit ledger" icon="◌" active={view === "ledger"} onClick={() => setView("ledger")} />
          <Nav label="Controls" icon="◇" active={view === "settings"} onClick={() => setView("settings")} />
        </nav>
        <div className="sidebar-foot"><i /> Sandbox connected<br /><span>Razorpay adapter · demo mode</span></div>
      </aside>

      <section className="content">
        <header>
          <div><p className="eyebrow">{view === "command" ? "RECOVERY OVERVIEW" : "WORKSPACE"}</p><h1>{heading[0]}</h1><p className="sub">{heading[1]}</p></div>
          <div className="header-actions">
            <button className="secondary" onClick={resetDemo}>Reset demo</button>
            <button className="primary" disabled={running || !autopilot} onClick={runRecovery}>{running ? "Running recovery…" : "Run recovery batch"}</button>
          </div>
        </header>
        <div className="notice"><span>✦</span>{notice}</div>

        {view === "command" && <Command metrics={metrics} events={events} audit={audit} onSelect={setSelected} />}
        {view === "queue" && <Queue events={events} onSelect={setSelected} />}
        {view === "playbooks" && <Playbooks />}
        {view === "ledger" && <Ledger audit={audit} />}
        {view === "settings" && <Settings autopilot={autopilot} setAutopilot={setAutopilot} onReplayWebhook={replayDemoWebhook} />}
      </section>

      {selected && <CaseDetail data={selected} onClose={() => setSelected(null)} />}
    </main>
  );
}

function Nav({ label, icon, badge, active, onClick }: { label: string; icon: string; badge?: number; active: boolean; onClick: () => void }) {
  return <button className={active ? "nav-active" : ""} onClick={onClick}><span>{icon}</span>{label}{badge !== undefined && <b>{badge}</b>}</button>;
}

function Command({ metrics, events, audit, onSelect }: { metrics: Metrics; events: RecoveryCase[]; audit: Audit[]; onSelect: (event: RecoveryCase) => void }) {
  const percent = metrics.total_at_risk ? Math.round(metrics.recovered / metrics.total_at_risk * 100) : 0;
  return <>
    <div className="metric-grid">
      <Metric label="Revenue at risk" value={money(metrics.total_at_risk)} note={`Across ${events.length} detected events`} tone="rose" icon="↘" />
      <Metric label="Recovery confirmed" value={money(metrics.recovered)} note={`${metrics.recovery_rate}% of exposed value`} tone="green" icon="↗" />
      <Metric label="Active interventions" value={String(metrics.active_cases)} note="Safe actions still in progress" tone="blue" icon="◎" />
      <Metric label="Human review" value={String(metrics.protected_cases)} note="Stopped by policy, not ignored" tone="gold" icon="◈" />
    </div>
    <div className="dashboard-grid">
      <section className="panel impact">
        <div className="panel-title"><div><p className="eyebrow">BATCH IMPACT</p><h2>Money brought back</h2></div><span className="pill">SANDBOX</span></div>
        <div className="impact-value">{money(metrics.recovered)} <span>confirmed</span></div>
        <div className="progress"><i style={{ width: `${percent}%` }} /></div>
        <div className="impact-bottom"><span>Recovery rate <b>{metrics.recovery_rate}%</b></span><span>{money(metrics.total_at_risk - metrics.recovered)} awaiting a safe next step</span></div>
        <div className="explain"><b>What this means</b><span>Recovered only moves after the adapter receives a confirmed payment outcome. It is not a predicted number.</span></div>
      </section>
      <section className="panel">
        <div className="panel-title"><div><p className="eyebrow">BEFORE WE ACT</p><h2>Three non-negotiables</h2></div><span className="shield">✓</span></div>
        <Guard title="Contact permission" text="No consent, no message or call." />
        <Guard title="Retry limit" text="Two automated attempts maximum." />
        <Guard title="Evidence trail" text="Each action gets a traceable record." />
      </section>
    </div>
    <section className="panel queue">
      <div className="panel-title"><div><p className="eyebrow">START HERE</p><h2>What RecoverIQ sees right now</h2></div><span className="queue-caption">Select a customer to see the explanation</span></div>
      <Queue events={events.slice(0, 4)} onSelect={onSelect} compact />
    </section>
    <div className="lower-grid">
      <section className="panel"><div className="panel-title"><div><p className="eyebrow">LATEST EVIDENCE</p><h2>Decision trail</h2></div><span className="hash"># hash-chained</span></div><LedgerRows audit={audit.slice(0, 4)} /></section>
      <section className="panel workflow"><p className="eyebrow">HOW A CASE MOVES</p><h2>Simple for your team. Safe for customers.</h2><div className="steps"><span><b>01</b> Identify the payment signal</span><span><b>02</b> Choose an approved playbook</span><span><b>03</b> Check consent and limits</span><span><b>04</b> Act, confirm, and log</span></div></section>
    </div>
  </>;
}

function Queue({ events, onSelect, compact = false }: { events: RecoveryCase[]; onSelect: (event: RecoveryCase) => void; compact?: boolean }) {
  if (!events.length) return <section className="panel empty-state">Waiting for the recovery adapter to send cases.</section>;
  return <div className={compact ? "" : "panel queue"}>{!compact && <div className="panel-title"><div><p className="eyebrow">PRIORITIZED BY RECOVERY POTENTIAL</p><h2>All cases</h2></div><span className="queue-caption">{events.length} accounts</span></div>}<div className="table-wrap"><table><thead><tr><th>Customer / event</th><th>Signal</th><th>Recommended action</th><th>Value</th><th>State</th></tr></thead><tbody>{events.map(event => <tr key={event.event_id}><td><button className="case-link" onClick={() => onSelect(event)}><strong>{event.customer}</strong><small>{event.event_id} · {event.channel} · {event.created_at}</small></button></td><td><span className={`risk ${event.risk_score > 80 ? "high" : event.risk_score > 65 ? "medium" : "low"}`}>{event.risk_score} score</span><small>{event.error_code.replaceAll("_", " ")}</small></td><td><span className="decision">{event.decision || "Awaiting triage"}</span><small>{event.guardrail || `Preferred: ${event.preferred_channel}`}</small></td><td className="amount">{money(event.amount)}</td><td><span className={`status ${event.status}`}>{event.status === "human_review" ? "Human review" : event.status}</span></td></tr>)}</tbody></table></div></div>;
}

function Playbooks() {
  const plays = [
    ["Insufficient balance", "UPI AutoPay", "Wait for the known salary window, then retry once.", "No rapid retries. Customer stays in control."],
    ["Mandate revoked", "UPI AutoPay", "Send a secure re-authentication link over the preferred channel.", "Never asks for UPI PIN or sensitive credentials."],
    ["Checkout abandoned", "Checkout", "Offer an expiry-bound payment link with the original cart context.", "One reminder only unless consent allows more."],
    ["Invoice overdue", "B2B receivables", "Prepare a concise follow-up and route the conversation to an owner.", "High-friction cases are reviewed by a human."],
  ];
  return <div className="playbook-grid">{plays.map(([name, channel, action, boundary]) => <section className="panel playbook" key={name}><span className="play-icon">↗</span><p className="eyebrow">{channel}</p><h2>{name}</h2><div><b>Action</b><p>{action}</p></div><div><b>Boundary</b><p>{boundary}</p></div><span className="policy-chip">Policy enforced</span></section>)}</div>;
}

function Ledger({ audit }: { audit: Audit[] }) { return <section className="panel ledger-full"><div className="panel-title"><div><p className="eyebrow">TAMPER-EVIDENT RECORD</p><h2>Every decision, in order</h2></div><span className="hash"># SHA-256 chain</span></div><LedgerRows audit={audit} /></section>; }
function LedgerRows({ audit }: { audit: Audit[] }) { return <>{audit.map((entry, index) => <div className="ledger-row" key={`${entry[4]}-${index}`}><em /><div><b>{entry[2].replaceAll("_", " ")}</b><small>{entry[1]} · {entry[3]}</small></div><code>{entry[4]?.slice(0, 10)}</code></div>)}{!audit.length && <p className="empty">Run a batch to generate the first decision records.</p>}</>; }

function Settings({ autopilot, setAutopilot, onReplayWebhook }: { autopilot: boolean; setAutopilot: (value: boolean) => void; onReplayWebhook: () => void }) {
  return <div className="settings-grid"><section className="panel"><p className="eyebrow">MODE</p><h2>Automation</h2><Toggle label="Run approved playbooks automatically" text="Only after consent and retry rules are checked." checked={autopilot} onChange={setAutopilot} /><Toggle label="Notify on protected cases" text="Tell the assigned team member when human review is needed." checked={true} onChange={() => {}} /></section><section className="panel"><p className="eyebrow">DEMO INTEGRATION</p><h2>Razorpay-compatible event source</h2><div className="source"><span>R</span><div><b>Webhook lifecycle simulator</b><small>Real receiver ready at /api/webhooks/razorpay</small></div><i>Demo</i></div><p className="integration-note">Replay a Razorpay-shaped payment failure. It goes through the same case-normalization path, but stays local and never needs an account or customer data.</p><button className="secondary test-event" onClick={onReplayWebhook}>Replay payment failure webhook</button></section></div>;
}

function CaseDetail({ data, onClose }: { data: RecoveryCase; onClose: () => void }) {
  const stopped = data.status === "human_review";
  const reason = data.error_code === "S005" ? "The debit failed because the account balance was insufficient." : data.error_code === "S008" ? "The customer’s UPI mandate is no longer valid." : data.error_code === "CHECKOUT_ABANDONED" ? "The customer left before completing checkout." : "The invoice crossed its due date.";
  return <div className="drawer-backdrop" onMouseDown={onClose}><aside className="drawer" onMouseDown={event => event.stopPropagation()}><button className="close" onClick={onClose}>×</button><p className="eyebrow">CASE EXPLAINER</p><h2>{data.customer}</h2><p className="drawer-meta">{data.event_id} · {data.channel} · {money(data.amount)}</p><span className={`status ${data.status}`}>{stopped ? "Human review needed" : data.status}</span><div className="detail-block"><b>What happened</b><p>{reason}</p></div><div className="detail-block"><b>What RecoverIQ will do</b><p>{data.decision || "Classify this event and select an approved playbook."}</p></div><div className="detail-block"><b>What the customer experiences</b><p>{stopped ? "Nothing automatically. This case is paused to protect the customer and is waiting for a team member." : `A clear, consented ${data.preferred_channel} message — never a surprise collection attempt.`}</p></div><div className="detail-block safe"><b>Safety check</b><p>{data.guardrail || "Consent and retry policy will be checked before any outreach."}</p></div></aside></div>;
}

function Metric({ label, value, note, tone, icon }: { label: string; value: string; note: string; tone: string; icon: string }) { return <section className={`metric ${tone}`}><div className="metric-icon">{icon}</div><p>{label}</p><h2>{value}</h2><small>{note}</small></section>; }
function Guard({ title, text }: { title: string; text: string }) { return <div className="guard"><span>✓</span><div><b>{title}</b><small>{text}</small></div></div>; }
function Toggle({ label, text, checked, onChange }: { label: string; text: string; checked: boolean; onChange: (value: boolean) => void }) { return <label className="toggle"><input type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)} /><span /><div><b>{label}</b><small>{text}</small></div></label>; }
