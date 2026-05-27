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
// IMPORTANT — timestamp encoding:
// Row 1  (ORDER BY ctid): the absolute Unix base timestamp in milliseconds (T0).
//                         e.g. 1257254615806 = 2009-11-03 13:23:35.806 UTC.
// Rows 2..N             : milliseconds elapsed since T0 (cumulative offset from T0).
//                         These values already represent TOTAL elapsed time —
//                         they are NOT per-row deltas from the previous row.
//
// Correct recovery:  absolute_ms = T0 + raw_ts   (rows 2..N; row 1 excluded)
// WRONG pattern:     DO NOT use a running SUM() window over raw_ts — those offsets
//                    are already cumulative, so summing them produces wildly wrong
//                    results (~10^12 instead of the correct ~10^6 range).
//
// Actual capture span: ~954 s ≈ 16 minutes (confirmed by querying the data).
// Expected bucket counts: 5-min → 4 buckets; 10-min → 2 buckets.

const NETWORK90MINS_SCHEMA_CONTEXT = `## Schema — Network90MinsData (PostgreSQL)

IMPORTANT: Always use schema-qualified names exactly as shown below.
Example: net90.traffic_90min, net90.ip_map, net90.event_type_mapping

This dataset is a ~16-minute capture of network flow records with attack labels.
All three tables live in the same schema (net90) and the main fact table is
net90.traffic_90min; the other two are small lookup tables that decode the
integer src_ip / dst_ip / attack columns into human-readable values.

---

### net90.traffic_90min
Per-flow connection records covering a single capture window (~16 minutes).
One row per network flow.

- timestamp (bigint) — RELATIVE-TIME ENCODED:
    Row 1 (first by ctid): absolute Unix time in **milliseconds since epoch**
                           (T0, the base timestamp, e.g. 1257254615806).
    Rows 2..N            : total milliseconds elapsed since T0 (cumulative offset
                           from the base, NOT a per-row delta from the previous row).
                           These values increase monotonically from 0 up to ~954,230 ms.
    Recovery:  absolute_time_ms = T0 + raw_ts   (for rows 2..N)
               absolute_time_ms = T0              (for row 1, where raw_ts = T0)
    CRITICAL: do NOT apply a running SUM() window — the offsets are already cumulative.
              Adding them up produces ~10^12 instead of the correct ~10^6 range.
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

## Recovering absolute timestamps (canonical pattern)

Row 1 holds the absolute base T0 (ms). Rows 2..N hold the total ms elapsed since T0.
The correct recovery is a simple addition — no window function or running sum:

WITH base AS (
  -- First row by ctid holds the absolute base timestamp
  SELECT timestamp AS base_ms FROM net90.traffic_90min ORDER BY ctid LIMIT 1
)
SELECT
  to_timestamp((b.base_ms + t.timestamp) / 1000.0) AT TIME ZONE 'UTC' AS event_time_utc,
  t.src_ip, t.dst_ip, t.attack
FROM net90.traffic_90min t
CROSS JOIN base b
WHERE t.timestamp < b.base_ms  -- exclude row 1 (its raw value IS T0, not an offset)
ORDER BY t.timestamp;

Notes:
- The WHERE t.timestamp < b.base_ms filter removes row 1 (whose raw_ts equals T0,
  not a small offset). All other rows have raw_ts well below T0 (max ~954,230).
- The capture spans ~954 seconds (~16 minutes), starting 2009-11-03 13:23 UTC.
- 5-minute buckets produce at most 4 distinct values; 10-min at most 2.
- WRONG: SUM(CASE WHEN rn=1 THEN 0 ELSE raw_ts END) OVER (ORDER BY rn) — this
  re-accumulates already-cumulative offsets and inflates the result to ~10^12.

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

-- Event distribution across the entire capture window
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

-- Time-bucketed activity (5-minute buckets, src->dst connection counts):
-- Expected: 4 distinct time_bucket values for the ~16-minute capture.
WITH base AS (
  SELECT timestamp AS base_ms FROM net90.traffic_90min ORDER BY ctid LIMIT 1
)
SELECT
  FLOOR((b.base_ms + t.timestamp) / (5.0 * 60 * 1000))::int AS time_bucket,
  s.ip_address AS source,
  d.ip_address AS target,
  COUNT(*) AS value
FROM net90.traffic_90min t
CROSS JOIN base b
JOIN net90.ip_map s ON s.ip_id = t.src_ip
JOIN net90.ip_map d ON d.ip_id = t.dst_ip
WHERE t.timestamp < b.base_ms
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3;

-- For 10-minute buckets: replace (5.0 * 60 * 1000) with (10.0 * 60 * 1000)
-- Expected: 2 distinct time_bucket values.

---

## Gotchas
- DO NOT use SUM() OVER (ORDER BY rn) on the timestamp column.
  The offsets in rows 2..N are already cumulative (total ms from T0). Summing
  them again produces ~10^12 and inflates 4 expected buckets to hundreds of thousands.
- The correct pattern is simply: absolute_ms = T0 + raw_ts  (no window function).
- Exclude row 1 when bucketing: WHERE t.timestamp < b.base_ms (row 1's raw value
  equals T0, not an offset; including it assigns it to the wrong bucket).
- attack = -1 means benign / "no attack", but it IS a real row in
  net90.event_type_mapping (event_code = -1 with the benign label). Use a plain
  INNER JOIN — do NOT filter -1 out. Filter only when you specifically want
  attacks-only or benign-only subsets, e.g. \`WHERE t.attack <> -1\` for
  attacks-only or \`WHERE t.attack = -1\` for benign-only.
- src_ip and dst_ip are integer IDs, not IP strings — you must JOIN through
  net90.ip_map (on ip_id) to get dotted-quad addresses.
- protocol is the IANA IP protocol number; translate 1/6/17 to ICMP/TCP/UDP for
  human-readable output.
- The capture covers a single ~16-minute window, so any "per-day" or
  "month-over-month" aggregation is meaningless on this dataset.`;
