// VAST1Data schema — sourced from the live PostgreSQL database.
// Edit this file to update the AI's schema knowledge; the HTML loads it at startup.
// Prompt caching (cache_control: ephemeral) is applied in the HTML so this block
// is only billed once per cache TTL (~5 min), not on every message.
//
// Naming conventions in this PostgreSQL dataset:
//   schema : mc1
//   tables : communications, participants, rounds
//   columns: snake_case (round_id, message_index, message_type, agent_role ...)

const VAST1DATA_SCHEMA_CONTEXT = `## Schema — VAST1Data (PostgreSQL)

IMPORTANT: Always use schema-qualified names exactly as shown below.
Example: mc1.communications, mc1.participants, mc1.rounds

---

### mc1.rounds
Round-level context table (one row per simulation round).
- round_id (bigint, nullable in DDL) — logical round key (1..23)
- hour (text, nullable) — ISO-like round timestamp string (e.g. 2046-05-17T09:00:00)
- environment_context (text, nullable) — round narrative/context payload, often JSON-like text
- Row count: ~23 rows
- Round/time range: round_id 1..23, hour 2046-05-17T09:00:00 to 2046-06-05T18:00:00

### mc1.participants
Participant roster/actions per round.
- round_id (bigint, nullable) — logical FK to mc1.rounds.round_id
- participant_index (bigint, nullable) — per-round participant sequence/index
- agent_id (text, nullable) — logical agent key (e.g. legal_agent, quality_agent); in current data this is 1:1 with agent_role
- agent_role (text, nullable) — role label (legal, social_media, platform_trust, pr, pr_intern, intern, judge); in current data this is 1:1 with agent_id
- agent_label (text, nullable) — display name (e.g. Legal-Agent)
- declared_action (text, nullable) — action summary; often empty, short status tokens, or long free text
- agent_round_metadata (text, nullable) — per-agent metadata payload (often JSON-like text)
- Row count: ~100 rows
- Round range: 1..23
- Distinct agents: 7

### mc1.communications
Message-level communication log across channels.
- round_id (bigint, nullable) — logical FK to mc1.rounds.round_id
- message_index (bigint, nullable) — sequence index within a round
- message_id (text, nullable) — message identifier (appears unique in current data)
- agent_id (text, nullable) — sender agent id; logically joins to mc1.participants on (round_id, agent_id)
- agent_role (text, nullable) — sender role
- agent_label (text, nullable) — sender display label
- internal_state (text, nullable) — state payload, commonly JSON-like text
- channel (text, nullable) — communication channel
  Values seen: comms_huddle, one_on_one_chat, side_huddle, personal_post, official_post, anonymous_post
- recipients (text, nullable) — recipient list payload (JSON array string, e.g. ["ALL"]). This joins to mc1.participants.agent_role for private messages, but may be "ALL" or other values for broadcasts.
- message_type (text, nullable) — message classification
  Values seen: broadcast, one_on_one_chat, side_huddle, action, public_post
- responding_to (text, nullable) — parent message_id for thread/reply chains
- content (text, nullable) — full message body
- timestamp (text, nullable) — ISO-like message timestamp string (e.g. 2046-05-17T09:01:00)
- Row count: ~912 rows
- Round range: 1..23
- Timestamp range: 2046-05-17T09:00:00 to 2046-06-05T18:55:00

---

## Data Integrity Notes
- No PRIMARY KEY / FOREIGN KEY / UNIQUE constraints are declared in information_schema.
- Logical integrity is strong in current data:
  - participants rows missing matching round: 0
  - communications rows missing matching round: 0
  - communications rows missing matching participant (by round_id + agent_id): 0
- agent_id <-> agent_role is a strict 1:1 mapping in current data (0 violations both directions in participants and communications).
- Distinct counts match: 7 agent_id values and 7 agent_role values.
- message_id appears unique in current snapshot (912 distinct of 912 rows), but not DB-enforced.

---

## Agent vs Role Semantics (Important)
- Treat agent_id and agent_role as alternate labels for the SAME entity set in this dataset.
- For connection/time-series queries, choose ONE grouping key per query: either agent_id or agent_role.
- Do NOT build edges at both levels in the same result and do NOT sum agent-level and role-level outputs together; this double-counts the same communications.
- If asked for "communications between roles over time", project to roles directly (sender role + recipient role) instead of joining role mappings again from participants.

---

## Key Relationships (logical, not enforced by constraints)
- mc1.participants.round_id -> mc1.rounds.round_id
- mc1.communications.round_id -> mc1.rounds.round_id
- mc1.communications.(round_id, agent_id) -> mc1.participants.(round_id, agent_id)
- mc1.communications.responding_to -> mc1.communications.message_id (reply/thread chain)

---

## Working with Text-Encoded Structure
Several fields may contain JSON/text payloads (environment_context, agent_round_metadata,
internal_state, recipients). Parse with ::jsonb when needed and when data is valid JSON.

-- Parse recipients array text:
SELECT message_id, jsonb_array_elements_text(recipients::jsonb) AS recipient
FROM mc1.communications
WHERE recipients IS NOT NULL;

-- Parse internal state JSON when present:
SELECT message_id, internal_state::jsonb
FROM mc1.communications
WHERE internal_state IS NOT NULL;

-- Convert text timestamp safely for time filtering/bucketing:
SELECT date_trunc('hour', timestamp::timestamp) AS hour_bucket, COUNT(*)
FROM mc1.communications
WHERE timestamp IS NOT NULL
GROUP BY hour_bucket
ORDER BY hour_bucket;

---

## Common Query Patterns
- Message volume over time: GROUP BY date_trunc('hour', timestamp::timestamp)
- Channel usage: GROUP BY channel ORDER BY COUNT(*) DESC
- Agent activity (canonical): GROUP BY agent_id ORDER BY COUNT(*) DESC
- Role activity (equivalent projection): GROUP BY agent_role ORDER BY COUNT(*) DESC
- Communication edges over time: aggregate by sender/recipient using either agent_id OR agent_role (not both)
- Thread reconstruction: self-join communications on responding_to = message_id
- Per-round narrative timeline: JOIN communications to rounds by round_id and ORDER BY message_index
- Participant action tracking: JOIN participants + communications by (round_id, agent_id)

---

## Gotchas
- hour and timestamp are text columns, not native timestamp types; cast explicitly when doing time math.
- The schema does not enforce keys; use logical joins carefully and validate assumptions in SQL.
- agent_id and agent_role are 1:1 in this dataset; combining both as separate entity layers in network/edge queries creates semantic duplicates.
- declared_action can contain long free text; for categorical analysis, normalize with CASE/LIKE or split patterns.
- recipients/internal_state payloads are text; cast to ::jsonb only when values are valid JSON.`;
