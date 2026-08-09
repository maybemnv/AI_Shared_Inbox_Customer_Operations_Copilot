-- Run after 001_initial.sql in a Supabase project.
-- This seed is a durable-schema companion to fixtures/freight_delay.json;
-- the local demo still seeds through app.fixture.create_demo_inbox().

insert into public.workspaces (id, name)
values ('demo-workspace', 'Freight Operations Demo')
on conflict (id) do update set name = excluded.name;

insert into public.connectors (id, workspace_id, kind, mode, status, capabilities)
values (
  'fixture-gmail', 'demo-workspace', 'gmail', 'fixture', 'available',
  '{"inbound":"fixture","outbound":"fixture_only","live":"not_configured"}'::jsonb
)
on conflict (id) do update set capabilities = excluded.capabilities;

insert into public.customers (id, workspace_id, external_id, name, primary_address)
values ('customer-jordan-lee', 'demo-workspace', null, 'Jordan Lee', 'jordan@example.test')
on conflict (id) do update set name = excluded.name;

insert into public.conversations (
  id, workspace_id, customer_id, connector_id, provider_account_id,
  provider_thread_id, channel, subject, status, priority, request_type,
  confidence, owner_id, queue_id, sla_state, version
)
values (
  'conversation-ft-204', 'demo-workspace', 'customer-jordan-lee', 'fixture-gmail',
  'fixture-gmail-account', 'thread-ft-204', 'email',
  'Shipment FT-204 is delayed', 'open', 'high', 'shipment_delay', 0.98,
  'operator-freight', 'freight-operations', 'not_started', 1
)
on conflict (id) do update set updated_at = now();

insert into public.inbound_events (workspace_id, provider_account_id, provider_event_id, conversation_id, payload)
values (
  'demo-workspace', 'fixture-gmail-account', 'event-ft-204', 'conversation-ft-204',
  '{"raw_reference":"fixture://freight-delay/FT-204"}'::jsonb
)
on conflict (workspace_id, provider_account_id, provider_event_id) do nothing;

insert into public.messages (
  id, workspace_id, conversation_id, provider_account_id, provider_thread_id,
  provider_message_id, direction, sender, recipients, subject, body_text,
  occurred_at, received_at, raw_reference
)
values (
  'message-message-ft-204', 'demo-workspace', 'conversation-ft-204',
  'fixture-gmail-account', 'thread-ft-204', 'message-ft-204', 'inbound',
  '{"external_id":null,"name":"Jordan Lee","address":"jordan@example.test"}'::jsonb,
  '[{"name":"Freight Operations","address":"ops@example.test"}]'::jsonb,
  'Shipment FT-204 is delayed',
  'Our freight shipment FT-204 has not arrived. Please confirm the new delivery date.',
  '2026-08-04T12:00:00Z', '2026-08-04T12:00:05Z', 'fixture://freight-delay/FT-204'
)
on conflict (id) do nothing;

insert into public.assignment_rules (id, workspace_id, priority, conditions, target)
values
  ('rule-shipment-delay', 'demo-workspace', 10, '{"request_type":"shipment_delay"}', '{"queue_id":"freight-operations","owner_id":"operator-freight"}'),
  ('rule-fallback-unassigned', 'demo-workspace', 1000, '{}', '{"queue_id":"queue-unassigned","owner_id":null}')
on conflict (id) do nothing;
