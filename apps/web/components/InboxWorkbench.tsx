"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  approveDraft,
  claimConversation,
  Conversation,
  editDraft,
  getConversation,
  listConversations,
  resolveConversation,
  runDraft,
  sendDraft,
  startSla,
} from "../lib/api";

const navItems = [
  ["Inbox", "/inbox"],
  ["Customers", "/customers/demo-customer"],
  ["Rules", "/rules"],
  ["Analytics", "/analytics"],
  ["Integrations", "/settings/integrations"],
];

function stateClass(value: string | null | undefined) {
  const normalized = value?.toLowerCase().replaceAll("_", "-") ?? "neutral";
  return `state-pill state-${normalized}`;
}

function formatDate(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function InboxWorkbench({
  initialConversationId,
}: {
  initialConversationId?: string;
}) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [draftBody, setDraftBody] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = async (id?: string) => {
    setLoading(true);
    setError(null);
    try {
      const items = await listConversations();
      setConversations(items);
      const target = id ?? initialConversationId ?? items[0]?.id;
      if (target) {
        const detail = await getConversation(target);
        setSelected(detail);
        setDraftBody(detail.draft?.body ?? "");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "API unavailable");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // The demo intentionally loads the persisted fixture snapshot once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialConversationId]);

  const openConversation = async (id: string) => {
    setError(null);
    try {
      const detail = await getConversation(id);
      setSelected(detail);
      setDraftBody(detail.draft?.body ?? "");
      window.history.replaceState(null, "", `/inbox/${id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Conversation unavailable");
    }
  };

  const execute = async (action: () => Promise<unknown>, success: string) => {
    if (!selected) return;
    setWorking(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      setNotice(success);
      await load(selected.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Command failed");
    } finally {
      setWorking(false);
    }
  };

  const openCount = conversations.filter((item) => item.status === "open").length;
  const highPriorityCount = conversations.filter((item) => item.priority === "high").length;
  const activeOwner = selected?.owner_id ?? "unassigned";
  const latestMessage = selected?.messages[selected.messages.length - 1];
  const draft = selected?.draft;
  const hasMissingEvidence = Boolean(draft?.missing_evidence.length);

  const canApprove = draft?.state === "approval_required" || draft?.state === "edited";
  const canSend = draft?.state === "approved" && Boolean(draft.approval);

  const selectedLabel = useMemo(
    () => selected?.subject ?? "No conversation selected",
    [selected],
  );

  return (
    <main className="shell">
      <header className="shell-header">
        <div className="brand-lockup">
          <span className="brand-mark">AO</span>
          <div>
            <div className="eyebrow">Customer operations</div>
            <div className="brand-name">Shared inbox copilot</div>
          </div>
        </div>
        <div className="mode-pill" aria-label="Fixture mode; live provider is not configured">
          <span className="mode-dot" aria-hidden="true" />
          Fixture mode · live unconfigured
        </div>
      </header>

      <nav className="top-nav" aria-label="Primary navigation">
        {navItems.map(([label, href]) => (
          <Link className={`nav-link ${href === "/inbox" ? "active" : ""}`} href={href} key={href}>
            {label}
          </Link>
        ))}
      </nav>

      <div className="workbench">
        <section className="page-heading">
          <div className="page-heading-copy">
            <div className="eyebrow">Workspace / freight operations</div>
            <h1>Inbox, with the next safe action in view.</h1>
            <p>One seeded customer thread. Every assertion stays tied to a message, a fixture result, or an operator decision.</p>
          </div>
          <div className="connector-pill state-available">gmail · fixture</div>
        </section>

        <section className="stat-strip" aria-label="Persisted workspace facts">
          <div className="stat-cell"><span className="data-label">Open</span><strong className="stat-value">{openCount}</strong></div>
          <div className="stat-cell"><span className="data-label">High priority</span><strong className="stat-value">{highPriorityCount}</strong></div>
          <div className="stat-cell"><span className="data-label">SLA state</span><strong className="stat-value">{selected?.sla_state ?? "—"}</strong></div>
          <div className="stat-cell"><span className="data-label">Owner</span><strong className="stat-value">{activeOwner}</strong></div>
        </section>

        {error && <div className="error-banner" role="alert">{error}. The API is fixture-first; check FastAPI is running on port 8000.</div>}
        {notice && <div className="draft-warning" role="status">{notice}</div>}

        {loading ? (
          <div className="empty-state loading">Loading the workspace snapshot…</div>
        ) : (
          <section className="workbench-grid">
            <aside className="panel queue-panel" aria-label="Conversation queue">
              <div className="panel-header">
                <div><h2>Queue</h2><p>{conversations.length} persisted thread</p></div>
                <span className="mono muted">01</span>
              </div>
              <div className="conversation-list">
                {conversations.map((conversation) => (
                  <button
                    className={`conversation-row ${selected?.id === conversation.id ? "selected" : ""}`}
                    key={conversation.id}
                    onClick={() => void openConversation(conversation.id)}
                    type="button"
                  >
                    <span className="row-topline"><strong>{conversation.messages[0]?.sender.name ?? "Unknown sender"}</strong><span className="priority-pill priority-high">{conversation.priority}</span></span>
                    <span className="row-subject">{conversation.subject}</span>
                    <span className="row-meta"><span>{conversation.queue_id ?? "unassigned"}</span><span className={stateClass(conversation.sla_state)}>{conversation.sla_state}</span></span>
                  </button>
                ))}
              </div>
            </aside>

            <section className="panel thread-panel" aria-label="Conversation detail">
              {!selected ? (
                <div className="empty-state">Select a conversation to inspect the evidence and next action.</div>
              ) : (
                <>
                  <div className="detail-header">
                    <div className="eyebrow">Conversation / {selected.id}</div>
                    <h2>{selectedLabel}</h2>
                    <div className="detail-meta"><span>{selected.messages[0]?.sender.name}</span><span>·</span><span>{selected.messages[0]?.sender.address}</span><span>·</span><span className="mono">v{selected.version}</span></div>
                    <div className="action-row">
                      {!draft && <button className="button" disabled={working} onClick={() => void execute(() => runDraft(selected.id), "Evidence-backed draft generated.")} type="button">Run safe draft</button>}
                      {draft && <button className="button" disabled={working} onClick={() => void execute(() => runDraft(selected.id), "Draft context refreshed.")} type="button">Refresh AI view</button>}
                      <button className="button secondary" disabled={working} onClick={() => void execute(() => claimConversation(selected.id, selected.version), "Conversation claimed by demo operator.")} type="button">Claim</button>
                      {selected.sla_state === "not_started" && <button className="button secondary" disabled={working} onClick={() => void execute(() => startSla(selected.id, selected.version), "SLA timer started.")} type="button">Start SLA</button>}
                      {selected.status !== "resolved" && <button className="button secondary" disabled={working} onClick={() => void execute(() => resolveConversation(selected.id, selected.version), "Conversation resolved.")} type="button">Resolve</button>}
                    </div>
                  </div>

                  <div className="detail-section">
                    <div className="section-title-row"><h3>Inbound message</h3><span className="connector-pill">gmail · fixture</span></div>
                    {latestMessage && <article className="message-card"><div className="message-head"><strong>{latestMessage.sender.name}</strong><span>{formatDate(latestMessage.received_at)}</span></div><p>{latestMessage.body_text}</p></article>}
                  </div>

                  <div className="detail-section">
                    <div className="section-title-row"><h3>Classification & route</h3><span className={stateClass(selected.priority)}>{selected.priority} · {selected.confidence ?? "—"}</span></div>
                    <p>{selected.classification?.rationale ?? "Classification is not available."}</p>
                    <ul className="evidence-list"><li><strong>Type</strong><small>{selected.request_type}</small></li><li><strong>Evidence message</strong><small>{selected.classification?.evidence_message_ids.join(", ") ?? "—"}</small></li><li><strong>Route</strong><small>{selected.queue_id ?? "unassigned"} / {selected.owner_id ?? "no owner"}</small></li></ul>
                  </div>

                  {selected.summary && <div className="detail-section"><div className="section-title-row"><h3>Operator summary</h3><span className="mono muted">fixture summary</span></div><div className="summary-grid"><div className="summary-item"><strong>Issue</strong><p>{selected.summary.issue}</p></div><div className="summary-item"><strong>Ask</strong><p>{selected.summary.ask}</p></div><div className="summary-item"><strong>Known facts</strong><ul className="fact-list">{selected.summary.known_facts.map((fact) => <li key={fact}>{fact}</li>)}</ul></div><div className="summary-item"><strong>Next action</strong><p>{selected.summary.next_action}</p></div></div></div>}

                  <div className="detail-section">
                    <div className="section-title-row"><h3>Response draft</h3><span className={stateClass(draft?.state)}>{draft?.state ?? "not generated"}</span></div>
                    {!draft ? <p className="muted">No draft exists. Generation will create an editable response with evidence and missing-evidence warnings.</p> : <><div className="draft-warning">{hasMissingEvidence ? `Missing evidence: ${draft.missing_evidence.join(", ")}. The draft does not promise a delivery date.` : "Evidence complete for the supported fixture path."}</div><textarea aria-label="Editable response draft" className="draft-body" onChange={(event) => setDraftBody(event.target.value)} value={draftBody} /><div className="draft-toolbar"><span className="mono muted">draft v{draft.version} · {draft.recipient}</span><div className="action-row"><button className="button secondary" disabled={working || draftBody === draft.body} onClick={() => void execute(() => editDraft(draft.id, draftBody, draft.version), "Draft edited; approval reset.")} type="button">Save edit</button><button className="button" disabled={working || !canApprove} onClick={() => void execute(() => approveDraft(draft.id, draft.version), "Exact draft version approved.")} type="button">Approve v{draft.version}</button><button className="button" disabled={working || !canSend} onClick={() => void execute(() => sendDraft(draft.id, draft.approval!.approval_id), "Fixture send recorded; no live provider was called.")} type="button">Send approved</button></div></div></>}
                  </div>
                </>
              )}
            </section>

            <aside className="panel context-panel" aria-label="Evidence and activity context">
              {!selected ? <div className="empty-state">Context appears with a selected thread.</div> : <><div className="panel-header"><div><h2>Context rail</h2><p>Evidence before assertion</p></div><span className="mono muted">read-only</span></div><div className="context-item"><div className="context-label">Shipment</div><div className="context-value">{selected.extracted_entities?.shipment_id ?? "unknown"}</div><div className="muted">Tracking {selected.extracted_entities?.tracking_number ?? "unknown"}</div></div><div className="context-item"><div className="context-label">Customer / account</div><div className="context-value">{selected.extracted_entities?.customer_name ?? "unknown"}</div><div className="muted">Account: {selected.extracted_entities?.account_id ?? "not linked"}</div></div>{selected.context?.items.map((item) => <div className="context-item" key={item.source_id}><div className="context-label">{item.source_type} · fixture</div><div className="context-value">{item.label}</div><div className="muted">{item.data.status ?? "available"} · captured {formatDate(item.captured_at)}</div></div>)}<div className="context-item"><div className="context-label">Missing facts</div><ul className="fact-list">{(selected.context?.missing ?? selected.extracted_entities?.unresolved_fields ?? ["context not retrieved"]).map((item) => <li key={item}>{item}</li>)}</ul></div><div className="context-item"><div className="context-label">Activity</div><ul className="activity-list">{selected.activity.slice().reverse().slice(0, 7).map((item) => <li key={item.id}><strong>{item.type.replaceAll("_", " ")}</strong><small>#{item.sequence} · {formatDate(item.occurred_at)}</small></li>)}</ul></div></>}
            </aside>
          </section>
        )}
      </div>

      <footer className="inline-rule"><span>Human control boundary · generation, approval, and send are separate actions.</span><span className="mono">workspace: demo-workspace</span></footer>
    </main>
  );
}
