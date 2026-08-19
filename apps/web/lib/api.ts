export type Activity = {
  id: string;
  type: string;
  actor: { type: string; id: string | null };
  payload: Record<string, unknown>;
  occurred_at: string;
  sequence: number;
};

export type Conversation = {
  id: string;
  workspace_id: string;
  channel: string;
  provider_account_id: string;
  provider_thread_id: string;
  provider_message_id: string;
  status: string;
  priority: string;
  request_type: string;
  confidence: number | null;
  classification: {
    rationale: string;
    evidence_message_ids: string[];
  } | null;
  owner_id: string | null;
  queue_id: string | null;
  sla_state: string;
  sla: { due_at: string | null; warning_at: string | null } | null;
  escalation: { connector: string; state: string; reason: string } | null;
  version: number;
  subject: string | null;
  messages: Array<{
    id: string;
    sender: { name: string | null; address: string | null };
    body_text: string;
    occurred_at: string;
    received_at: string;
  }>;
  extracted_entities: {
    customer_name: string | null;
    account_id: string | null;
    shipment_id: string | null;
    tracking_number: string | null;
    requested_action: string | null;
    promised_date: string | null;
    unresolved_fields: string[];
  } | null;
  context: {
    state: string;
    items: Array<{
      source_type: string;
      source_id: string;
      label: string;
      captured_at: string;
      data: Record<string, string | null>;
    }>;
    missing: string[];
  } | null;
  summary: {
    issue: string;
    ask: string;
    known_facts: string[];
    missing_facts: string[];
    next_action: string;
  } | null;
  draft: Draft | null;
  activity: Activity[];
};

export type Draft = {
  id: string;
  version: number;
  recipient: string;
  subject: string | null;
  body: string;
  evidence: Array<{
    source_type: string;
    source_id: string;
    label: string;
    captured_at: string;
  }>;
  missing_evidence: string[];
  confidence: number;
  state: string;
  approval: { approval_id: string; draft_version: number } | null;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8103";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.message ?? `API request failed (${response.status})`);
  }
  return payload as T;
}

export async function listConversations(): Promise<Conversation[]> {
  const result = await request<{ items: Conversation[] }>(
    "/api/v1/conversations?workspace_id=demo-workspace",
  );
  return result.items;
}

export async function getConversation(id: string): Promise<Conversation> {
  return request<Conversation>(
    `/api/v1/conversations/${id}?workspace_id=demo-workspace`,
  );
}

export async function runDraft(id: string) {
  return request<{ draft: Draft }>(
    `/api/v1/conversations/${id}/ai/run`,
    { method: "POST", body: JSON.stringify({ action: "draft" }) },
  );
}

export async function claimConversation(id: string, version: number) {
  return request<Conversation>(`/api/v1/conversations/${id}/claim`, {
    method: "POST",
    body: JSON.stringify({
      workspace_id: "demo-workspace",
      actor_id: "demo-operator",
      expected_version: version,
    }),
  });
}

export async function startSla(id: string, version: number) {
  return request<Conversation>(`/api/v1/conversations/${id}/sla/start`, {
    method: "POST",
    body: JSON.stringify({
      workspace_id: "demo-workspace",
      actor_id: "system-sla",
      expected_version: version,
    }),
  });
}

export async function resolveConversation(id: string, version: number) {
  return request<Conversation>(`/api/v1/conversations/${id}/resolve`, {
    method: "POST",
    body: JSON.stringify({
      workspace_id: "demo-workspace",
      actor_id: "demo-operator",
      expected_version: version,
    }),
  });
}

export async function editDraft(id: string, body: string, version: number) {
  return request<Draft>(`/api/v1/drafts/${id}`, {
    method: "PATCH",
    body: JSON.stringify({
      workspace_id: "demo-workspace",
      actor_id: "demo-operator",
      body,
      expected_version: version,
    }),
  });
}

export async function approveDraft(id: string, version: number) {
  return request<{ approval_id: string; state: string }>(
    `/api/v1/drafts/${id}/approve`,
    {
      method: "POST",
      body: JSON.stringify({
        workspace_id: "demo-workspace",
        actor_id: "demo-operator",
        expected_version: version,
      }),
    },
  );
}

export async function sendDraft(id: string, approvalId: string) {
  return request<{ state: string; connector: string }>(
    `/api/v1/drafts/${id}/send`,
    {
      method: "POST",
      body: JSON.stringify({
        workspace_id: "demo-workspace",
        actor_id: "demo-operator",
        approval_id: approvalId,
        idempotency_key: `demo-send-${id}`,
      }),
    },
  );
}
