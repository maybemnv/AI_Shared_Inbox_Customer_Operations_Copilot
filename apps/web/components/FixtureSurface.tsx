"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getAnalytics, getCustomer, listConnectors, listRules } from "../lib/api";

const navItems = [["Inbox", "/inbox"], ["Customer", "/customers/customer-jordan-lee"], ["Rules", "/rules"], ["Integrations", "/settings/integrations"], ["Analytics", "/analytics"]];

function Shell({ children }: { children: React.ReactNode }) {
  return <main className="shell"><header className="shell-header"><div className="brand-lockup"><span className="brand-mark">AO</span><div><div className="eyebrow">Customer operations</div><div className="brand-name">Shared inbox copilot</div></div></div><div className="mode-pill">Fixture mode · live unconfigured</div></header><nav className="top-nav" aria-label="Primary navigation">{navItems.map(([label, href]) => <Link className="nav-link" href={href} key={href}>{label}</Link>)}</nav>{children}</main>;
}

function useFixture<T>(load: () => Promise<T>) {
  const [value, setValue] = useState<T | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => { void load().then(setValue).catch(() => setFailed(true)); }, []);
  return { value, failed };
}

function FixtureFailure() {
  return <p className="error-banner" role="alert">Fixture data is unavailable. Check the local fixture API and retry the route.</p>;
}

export function CustomerSurface() {
  const { value: customer, failed } = useFixture(() => getCustomer("customer-jordan-lee"));
  return <Shell><section className="panel workbench"><div className="eyebrow">Fixture account</div><h1>Customer profile</h1>{failed ? <FixtureFailure /> : customer ? <><p>{customer.name} · {customer.address}</p><h2>Linked conversations</h2>{customer.conversations.map((conversation) => <Link className="conversation-row" href={`/inbox/${conversation.id}`} key={conversation.id}>{conversation.subject}</Link>)}</> : <p>Loading fixture customer…</p>}</section></Shell>;
}

export function RulesSurface() {
  const { value, failed } = useFixture(listRules);
  return <Shell><section className="panel workbench"><div className="eyebrow">Fixture routing</div><h1>Assignment rules</h1>{failed ? <FixtureFailure /> : value ? value.items.map((rule) => <article className="context-item" key={rule.id}><strong>{rule.id}</strong><p>Priority {rule.priority} · {rule.enabled ? "enabled" : "disabled"}</p><small>{JSON.stringify(rule.conditions)} → {JSON.stringify(rule.target)}</small></article>) : <p>Loading fixture rules…</p>}</section></Shell>;
}

export function IntegrationsSurface() {
  const { value, failed } = useFixture(listConnectors);
  return <Shell><section className="panel workbench"><div className="eyebrow">No live providers</div><h1>Fixture connectors</h1>{failed ? <FixtureFailure /> : value ? value.items.map((connector) => <article className="context-item" key={connector.id}><strong>{connector.connector}</strong><p>{connector.status} · {connector.live_status}</p><small>Cursor: {connector.cursor ?? "not started"}</small></article>) : <p>Loading fixture connectors…</p>}</section></Shell>;
}

export function AnalyticsSurface() {
  const { value: analytics, failed } = useFixture(getAnalytics);
  return <Shell><section className="panel workbench"><div className="eyebrow">Event-derived fixture totals</div><h1>Operational analytics</h1>{failed ? <FixtureFailure /> : analytics ? <div className="stat-strip"><div className="stat-cell"><span className="data-label">Open</span><strong className="stat-value">{analytics.open_conversations}</strong></div><div className="stat-cell"><span className="data-label">High priority</span><strong className="stat-value">{analytics.high_priority_conversations}</strong></div><div className="stat-cell"><span className="data-label">Activity</span><strong className="stat-value">{analytics.activity_events}</strong></div></div> : <p>Loading fixture metrics…</p>}</section></Shell>;
}
