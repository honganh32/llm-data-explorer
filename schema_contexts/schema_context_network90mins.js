// Network90MinsData schema — sourced from the live PostgreSQL database.
// Edit this file to update the AI's schema knowledge; the HTML loads it at startup.
// Prompt caching (cache_control: ephemeral) is applied in the HTML so this block
// is only billed once per cache TTL (~5 min), not on every message.
//
// Naming conventions:
//   schema : net90
//   tables : traffic_90min, ip_map, event_type_mapping
//   columns: snake_case (timestamp, src_ip, dst_ip, attack …)
//
// IMPORTANT — timestamp encoding (read carefully before writing queries):
// The `timestamp` column in net90.traffic_90min is DELTA-ENCODED, not an absolute
// epoch on every row:
//   • Row 1 holds the absolute starting timestamp in milliseconds since epoch
//     (e.g. 1257254615806 = 2009-11-03 13:23:35.806 UTC = 2009-11-03 20:23:35.806+07).
//   • Every subsequent row's `timestamp` value is the UNIX time elapsed since the
//     immediately preceding row (i.e. row N stores t_N − t_{N-1}).
// To recover the absolute time of row N you must take the row-1 base and add a
// running sum of all deltas from rows 2..N — see "Recovering absolute timestamps"
// below. Treating `timestamp` as a raw epoch will silently produce wrong results.

const NETWORK90MINS_SCHEMA_CONTEXT = `## Schema — Network90MinsData (PostgreSQL)

IMPORTANT: Always use schema-qualified names exactly as shown below.
Example: net90.traffic_90min, net90.ip_map, net90.event_type_mapping

This dataset is a 90-minute capture of network flow records with attack labels.
All three tables live in the same schema (net90) and the main fact table is
net90.traffic_90min; the other two are small lookup tables that decode the
integer src_ip / dst_ip / attack columns into human-readable values.

---

### net90.traffic_90min
Per-flow connection records covering a single 90-minute window.
One row per network flow.

- timestamp (bigint) — DELTA-ENCODED time column.
    Row 1: absolute Unix time in **milliseconds since epoch**
           (e.g. 1257254615806 → 2009-11-03 13:23:35.806 UTC).
    Rows 2..N: elapsed Unix time since the previous row (i.e. a delta, not an
           absolute timestamp). To get the real time of row N you must add the
           running sum of deltas to the row-1 base. See "Recovering absolute
           timestamps" further down — never feed this column directly into
           to_timestamp() except for row 1.
- length (bigint) — flow length / size indicator (e.g. 66)
- src_ip (bigint, FK → net90.ip_map.ip_id) — integer ID of the source host
- dst_ip (bigint, FK → net90.ip_map.ip_id) — integer ID of the destination host
- protocol (bigint) — IP protocol number: 1=ICMP, 6=TCP, 17=UDP
- src_port (bigint) — source port (0–65535; ephemeral ports are typically ≥ 1024)
- dst_port (bigint) — destination port (well-known: 80=HTTP, 443=HTTPS, 53=DNS,
    25=SMTP, 22=SSH, 21=FTP, 23=Telnet)
- flags (bigint) — TCP flag bitmask / status indicator
- count (bigint) — packet or record count for this flow
- attack (bigint, FK → net90.event_type_mapping.event_code) — attack/event label.
    The value **-1 represents benign / "no attack"** and IS present as a row in
    net90.event_type_mapping (event_code = -1). All rows can be decoded with a
    plain INNER JOIN — no need to filter -1 out.

---

### net90.ip_map
Lookup table that decodes the integer src_ip / dst_ip values in
net90.traffic_90min into actual IP address strings.
- ip_id (bigint) — integer key referenced by traffic_90min.src_ip and traffic_90min.dst_ip
- ip_address (text) — IPv4 address in dotted-quad form (e.g. '10.0.0.5')

---

### net90.event_type_mapping
Lookup table that decodes the integer attack column in net90.traffic_90min
into a human-readable event/attack label.
- event_code (bigint) — integer key referenced by traffic_90min.attack.
    Includes a row with event_code = -1 representing benign / "no attack" traffic,
    so every value of traffic_90min.attack — including -1 — has a matching row.
- event_type (text) — name/description of the attack or event class
    (the row with event_code = -1 carries the benign label)

---

## Key Relationships
- net90.traffic_90min.src_ip   → net90.ip_map.ip_id
- net90.traffic_90min.dst_ip   → net90.ip_map.ip_id
- net90.traffic_90min.attack   → net90.event_type_mapping.event_code   (every value is matched, including -1 = benign)

---

## Recovering absolute timestamps from the delta-encoded \`timestamp\` column

Because only row 1 holds an absolute epoch (in milliseconds) and every following
row holds the delta from the previous row, you cannot use \`timestamp\` directly
as an epoch. Use a window-function running sum to reconstruct absolute times.

Assuming the table has a stable physical / insertion order you can rely on
(e.g. via a row number, a CTID-based ordering, or a separately stored row id),
the canonical recovery pattern is:

-- Reconstruct the absolute UTC timestamp for every row.
-- Row 1's value is treated as the absolute base (ms); rows 2..N are added as deltas.
WITH ordered AS (
  SELECT
    ROW_NUMBER() OVER (ORDER BY ctid) AS rn,   -- replace ORDER BY with a stable key if you have one
    timestamp AS raw_ts,
    length, src_ip, dst_ip, protocol,
    src_port, dst_port, flags, count, attack
  FROM net90.traffic_90min
),
base AS (
  SELECT raw_ts AS base_ms FROM ordered WHERE rn = 1
),
recovered AS (
  SELECT
    o.*,
    -- Sum of deltas from row 2 up to current row; row 1 contributes 0.
    SUM(CASE WHEN o.rn = 1 THEN 0 ELSE o.raw_ts END)
        OVER (ORDER BY o.rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        AS delta_sum
  FROM ordered o
)
SELECT
  r.rn,
  to_timestamp((b.base_ms + r.delta_sum) / 1000.0) AT TIME ZONE 'UTC' AS event_time_utc,
  r.length, r.src_ip, r.dst_ip, r.protocol,
  r.src_port, r.dst_port, r.flags, r.count, r.attack
FROM recovered r
CROSS JOIN base b
ORDER BY r.rn;

Notes on the unit of the deltas:
- The base in row 1 is in **milliseconds**.
- Whether each delta is itself in milliseconds or seconds depends on the data
  source. If recovered times look ~1000× too compressed, the deltas are in
  seconds — multiply them by 1000 before adding to the base. If they look
  ~1000× too spread out, divide by 1000. A 90-minute capture should span
  roughly 5,400,000 ms end-to-end; use that as a sanity check.
- Once recovered, divide by 1000 inside to_timestamp() because to_timestamp()
  takes seconds.

---

## Common Query Patterns

-- Decode IPs and attack labels for the first 100 flows
-- (every row matches an event_type, including the benign row with event_code = -1):
SELECT
  t.timestamp AS raw_ts,
  s.ip_address AS src,
  d.ip_address AS dst,
  t.protocol, t.src_port, t.dst_port,
  t.length, t.flags, t.count,
  e.event_type
FROM net90.traffic_90min t
JOIN net90.ip_map             s ON s.ip_id      = t.src_ip
JOIN net90.ip_map             d ON d.ip_id      = t.dst_ip
JOIN net90.event_type_mapping e ON e.event_code = t.attack
LIMIT 100;

-- Event distribution across the entire 90-minute window
-- (the benign label appears here as the event_type whose event_code = -1):
SELECT e.event_type, COUNT(*) AS flow_count
FROM net90.traffic_90min t
JOIN net90.event_type_mapping e ON e.event_code = t.attack
GROUP BY e.event_type
ORDER BY flow_count DESC;

-- Benign vs attack ratio:
SELECT
  SUM(CASE WHEN attack = -1 THEN 1 ELSE 0 END) AS benign_flows,
  SUM(CASE WHEN attack <> -1 THEN 1 ELSE 0 END) AS attack_flows
FROM net90.traffic_90min;

-- Top talkers (busiest source IPs):
SELECT s.ip_address, COUNT(*) AS flows, SUM(t.count) AS total_packets
FROM net90.traffic_90min t
JOIN net90.ip_map s ON s.ip_id = t.src_ip
GROUP BY s.ip_address
ORDER BY flows DESC;

-- Top targeted destinations / ports:
SELECT d.ip_address, t.dst_port, COUNT(*) AS flows
FROM net90.traffic_90min t
JOIN net90.ip_map d ON d.ip_id = t.dst_ip
GROUP BY d.ip_address, t.dst_port
ORDER BY flows DESC;

-- Protocol mix:
SELECT
  CASE protocol WHEN 1 THEN 'ICMP' WHEN 6 THEN 'TCP' WHEN 17 THEN 'UDP'
                ELSE protocol::text END AS proto,
  COUNT(*) AS flows
FROM net90.traffic_90min
GROUP BY protocol
ORDER BY flows DESC;

-- Time-bucketed activity (requires the absolute-timestamp recovery CTE above):
-- Wrap the recovery query as a subquery, then GROUP BY date_trunc('minute', event_time_utc).

---

## Gotchas
- DO NOT use to_timestamp(timestamp) on net90.traffic_90min directly — only row 1
  holds an epoch; every other row holds a delta. Recover absolute times with the
  window-function pattern above.
- attack = -1 means benign / "no attack", but it IS a real row in
  net90.event_type_mapping (event_code = -1 with the benign label). Use a plain
  INNER JOIN — do NOT filter -1 out. Filter only when you specifically want
  attacks-only or benign-only subsets, e.g. \`WHERE t.attack <> -1\` for
  attacks-only or \`WHERE t.attack = -1\` for benign-only.
- src_ip and dst_ip are integer IDs, not IP strings — you must JOIN through
  net90.ip_map (on ip_id) to get dotted-quad addresses.
- protocol is the IANA IP protocol number; translate 1/6/17 to ICMP/TCP/UDP for
  human-readable output.
- The capture covers a single 90-minute window, so any "per-day" or
  "month-over-month" aggregation is meaningless on this dataset.`;
