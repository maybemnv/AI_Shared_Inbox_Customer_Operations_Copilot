-- Supabase/Postgres durable boundary for the PRD entities.
-- The running prototype uses app.ingestion.InMemoryInbox until this schema,
-- RLS, and a transaction-backed repository are validated against a project.

create extension if not exists pgcrypto;

create table if not exists public.workspaces (
  id text primary key,
  name text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.workspace_members (
  workspace_id text not null references public.workspaces(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('admin', 'operator', 'viewer')),
  primary key (workspace_id, user_id)
);

create table if not exists public.connectors (
  id text primary key,
  workspace_id text not null references public.workspaces(id) on delete cascade,
  kind text not null check (kind in ('gmail', 'microsoft_graph', 'front', 'whatsapp')),
  mode text not null check (mode in ('live', 'fixture', 'blocked')),
  status text not null default 'available',
  cursor text,
  last_sync_at timestamptz,
  failure_reason text,
  capabilities jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.customers (
  id text primary key,
  workspace_id text not null references public.workspaces(id) on delete cascade,
  external_id text,
  name text,
  primary_address text,
  created_at timestamptz not null default now(),
  unique (workspace_id, external_id)
);

create table if not exists public.conversations (
  id text primary key,
  workspace_id text not null references public.workspaces(id) on delete cascade,
  customer_id text references public.customers(id) on delete set null,
  connector_id text references public.connectors(id) on delete set null,
  provider_account_id text not null,
  provider_thread_id text not null,
  channel text not null,
  subject text,
  status text not null default 'open',
  priority text not null default 'unknown',
  request_type text not null default 'unknown',
  confidence numeric check (confidence between 0 and 1),
  owner_id text,
  queue_id text,
  sla_state text not null default 'not_started',
  version integer not null default 1 check (version > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, provider_account_id, provider_thread_id)
);

create table if not exists public.inbound_events (
  workspace_id text not null references public.workspaces(id) on delete cascade,
  provider_account_id text not null,
  provider_event_id text not null,
  conversation_id text references public.conversations(id) on delete set null,
  payload jsonb not null,
  received_at timestamptz not null default now(),
  primary key (workspace_id, provider_account_id, provider_event_id)
);

create table if not exists public.messages (
  id text primary key,
  workspace_id text not null references public.workspaces(id) on delete cascade,
  conversation_id text not null references public.conversations(id) on delete cascade,
  provider_account_id text not null,
  provider_thread_id text not null,
  provider_message_id text not null,
  direction text not null check (direction in ('inbound', 'outbound')),
  sender jsonb not null,
  recipients jsonb not null default '[]'::jsonb,
  subject text,
  body_text text not null,
  occurred_at timestamptz not null,
  received_at timestamptz not null,
  raw_reference text not null,
  unique (workspace_id, provider_account_id, provider_message_id)
);

create table if not exists public.activity_events (
  id text primary key,
  workspace_id text not null references public.workspaces(id) on delete cascade,
  conversation_id text references public.conversations(id) on delete cascade,
  type text not null,
  actor jsonb not null,
  payload jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now(),
  sequence bigint not null,
  unique (conversation_id, sequence)
);

create table if not exists public.extracted_entity_sets (
  id uuid primary key default gen_random_uuid(),
  workspace_id text not null references public.workspaces(id) on delete cascade,
  conversation_id text not null references public.conversations(id) on delete cascade,
  conversation_version integer not null,
  payload jsonb not null,
  evidence_message_ids jsonb not null default '[]'::jsonb,
  confidence numeric not null check (confidence between 0 and 1),
  created_at timestamptz not null default now()
);

create table if not exists public.drafts (
  id text primary key,
  workspace_id text not null references public.workspaces(id) on delete cascade,
  conversation_id text not null references public.conversations(id) on delete cascade,
  version integer not null default 1 check (version > 0),
  channel text not null,
  recipient text not null,
  subject text,
  body text not null,
  evidence jsonb not null default '[]'::jsonb,
  missing_evidence jsonb not null default '[]'::jsonb,
  confidence numeric not null check (confidence between 0 and 1),
  state text not null check (state in ('generating', 'ready', 'edited', 'approval_required', 'approved', 'rejected', 'send_failed')),
  conversation_version integer not null,
  generated_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (conversation_id)
);

create table if not exists public.approvals (
  id text primary key,
  workspace_id text not null references public.workspaces(id) on delete cascade,
  draft_id text not null references public.drafts(id) on delete cascade,
  draft_version integer not null,
  approved_by uuid references auth.users(id) on delete set null,
  approved_at timestamptz not null default now(),
  unique (draft_id, draft_version)
);

create table if not exists public.outbound_actions (
  action_id text primary key,
  workspace_id text not null references public.workspaces(id) on delete cascade,
  conversation_id text not null references public.conversations(id) on delete cascade,
  draft_id text not null references public.drafts(id) on delete cascade,
  draft_version integer not null,
  connector_id text references public.connectors(id) on delete set null,
  approval_id text not null references public.approvals(id) on delete restrict,
  idempotency_key text not null,
  state text not null check (state in ('queued', 'sending', 'sent', 'failed')),
  provider_message_id text,
  failure_reason text,
  created_at timestamptz not null default now(),
  unique (workspace_id, idempotency_key)
);

create table if not exists public.sync_jobs (
  job_id text primary key,
  workspace_id text not null references public.workspaces(id) on delete cascade,
  connector_id text not null references public.connectors(id) on delete cascade,
  kind text not null,
  idempotency_key text not null,
  attempt integer not null default 1,
  state text not null,
  retryable boolean not null default false,
  cursor text,
  failure_reason text,
  created_at timestamptz not null default now(),
  unique (workspace_id, idempotency_key)
);

create table if not exists public.sla_instances (
  id uuid primary key default gen_random_uuid(),
  workspace_id text not null references public.workspaces(id) on delete cascade,
  conversation_id text not null unique references public.conversations(id) on delete cascade,
  policy_id text not null,
  state text not null,
  started_at timestamptz,
  warning_at timestamptz,
  due_at timestamptz,
  resolved_at timestamptz,
  escalation jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.assignment_rules (
  id text primary key,
  workspace_id text not null references public.workspaces(id) on delete cascade,
  priority integer not null,
  conditions jsonb not null default '{}'::jsonb,
  target jsonb not null default '{}'::jsonb,
  enabled boolean not null default true,
  version integer not null default 1,
  unique (workspace_id, priority, id)
);

create index if not exists conversations_workspace_status_idx on public.conversations (workspace_id, status, priority);
create index if not exists activity_workspace_sequence_idx on public.activity_events (workspace_id, sequence);
create index if not exists sync_jobs_workspace_state_idx on public.sync_jobs (workspace_id, state);

create or replace function public.current_workspace_id()
returns text
language sql
stable
as $$
  select nullif(current_setting('request.jwt.claims', true)::jsonb ->> 'workspace_id', '');
$$;

create or replace function public.is_workspace_member(target_workspace_id text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.workspace_members
    where workspace_id = target_workspace_id
      and user_id = auth.uid()
  );
$$;

alter table public.workspaces enable row level security;
alter table public.workspace_members enable row level security;
alter table public.connectors enable row level security;
alter table public.customers enable row level security;
alter table public.conversations enable row level security;
alter table public.inbound_events enable row level security;
alter table public.messages enable row level security;
alter table public.activity_events enable row level security;
alter table public.extracted_entity_sets enable row level security;
alter table public.drafts enable row level security;
alter table public.approvals enable row level security;
alter table public.outbound_actions enable row level security;
alter table public.sync_jobs enable row level security;
alter table public.sla_instances enable row level security;
alter table public.assignment_rules enable row level security;

-- The service role bypasses RLS. Authenticated client access requires the
-- workspace_id JWT claim and membership; no prototype client is granted this.
do $$
declare table_name text;
begin
  foreach table_name in array array['connectors','customers','conversations','inbound_events','messages','activity_events','extracted_entity_sets','drafts','approvals','outbound_actions','sync_jobs','sla_instances','assignment_rules'] loop
    execute format('drop policy if exists workspace_isolation on public.%I', table_name);
    execute format('create policy workspace_isolation on public.%I using (workspace_id = public.current_workspace_id() and public.is_workspace_member(workspace_id)) with check (workspace_id = public.current_workspace_id() and public.is_workspace_member(workspace_id))', table_name);
  end loop;
end $$;

drop policy if exists workspace_member_isolation on public.workspace_members;
create policy workspace_member_isolation on public.workspace_members
  using (workspace_id = public.current_workspace_id() and public.is_workspace_member(workspace_id))
  with check (workspace_id = public.current_workspace_id());
