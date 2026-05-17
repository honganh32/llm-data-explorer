// NetworkMonitoring schema — sourced from the live PostgreSQL database.
// Edit this file to update the AI's schema knowledge; the HTML loads it at startup.
// Prompt caching (cache_control: ephemeral) is applied in the HTML so this block
// is only billed once per cache TTL (~5 min), not on every message.
//
// Naming conventions:
//   schema : anomalies
//   table  : network_anomalies
//   columns: snake_case (event_type, c2s_id, source, destination …)

const NETWORK_MONITORING_SCHEMA_CONTEXT = `## Schema — NetworkMonitoring (PostgreSQL)

IMPORTANT: Always use schema-qualified names exactly as shown below.
Example: anomalies.network_anomalies

---

### anomalies.network_anomalies
- event_type (text, nullable) — classification of the network anomaly or attack scenario
- c2s_id (double precision, nullable) — unique identifier for the connection/event record
- source (text, nullable) — source IP address (IPv4)
- source_port_s (double precision, nullable) — source port number
- destination (text, nullable) — destination IP address (IPv4)
- destination_port_s (text, nullable) — destination port(s); may contain multiple space-separated ports
- start_time_utc (timestamp, nullable) — event start time in UTC
- stop_time_utc (timestamp, nullable) — event end time in UTC
- No primary key defined; c2s_id is the closest natural identifier but is not unique-constrained
- Row count: ~8,223 rows
- Date range: 2009-11-03 to 2009-11-13

---

## event_type Values
- break-DNS_1 /home/administrator/attack-scripts/sdu
- break-DNS_1_exploit echo
- c2 + control channel exfil - no precursor nc
- c2 + tcp control channel exfil - no precursor nc
- c2 + tcp control channel exfil exploit/malware/mal
- c2 exploit/malware/malclient.pl
- c2 heartbeat exploit/malware/malclient.pl
- c2 remote command execution nc
- c2+ tcp control channel exfil - no precursor nc
- c2+ tcp control channel exfil nc
- client compromise
- client compromise exfil/sams_launch_vulnerable_cli
- compromised_server
- ddos
- dns-rewrite /home/administrator/attack-scripts/sdu
- failed attack exploit/iis-asp-overflow
- failed attack framework-2.6/msfcli cabrightstor_di
- failed attack framework-2.6/msfcli iis_nsiislog_po
- failed attack framework-2.6/msfcli windows_ssl_pct
- failed attack or scan exploit/bin/iis_nsiislog.pl
- failed attack or scan exploit/bin/webstar_ftp_user
- malware ddos
- no precursor client compromise exfil/sams_launch_v
- noisy-blackhole_64-127 /home/administrator/attack-
- noisy-blackhole_exploit echo
- noisy c2+ tcp control channel exfil fork
- noisy c2+ tcp control channel exfil nc
- noisy client compromise + malicious download exfil
- noisy phishing email exploit/malware/trawler
- noisy phishing email exploit/malware/trawler.pl
- out2in
- out2in dns
- phishing email exploit/malware/trawler
- post-phishing c2 + tcp control channel exfil explo
- post-phishing c2 + tcp control channel exfil nc
- post-phishing c2 echo
- post-phishing c2 exploit/malware/malclient.pl
- post-phishing c2 heartbeat exploit/malware/malclie
- post-phishing client compromise + malicious downlo
- post-phishing icmp exfil nc
- post-phishing tcp exfil nc
- router-redirect /home/administrator/attack-scripts
- router-rewrite /home/administrator/attack-scripts/
- scan /usr/bin/nmap
- spam bot
- spambot client compromise
- spambot malicious download

---

## Common destination_port_s Values (top by frequency)
- 80 (HTTP) — 4,246 events
- 25 (SMTP) — 1,332 events
- 10000 — 642 events
- 53 (DNS) — 463 events
- 1257 3128 (multi-port) — 234 events
- 499 — 161 events
- 443 (HTTPS) — 55 events
- 0 — 54 events
- 8181 — 52 events
- 21 (FTP) — 49 events

---

## Common Query Patterns
- Attack distribution: GROUP BY event_type ORDER BY COUNT(*) DESC
- Top source IPs: GROUP BY source ORDER BY COUNT(*) DESC
- Top targeted destinations: GROUP BY destination ORDER BY COUNT(*) DESC
- Timeline analysis: GROUP BY DATE_TRUNC('hour', start_time_utc) ORDER BY hour
- Event duration: EXTRACT(EPOCH FROM (stop_time_utc - start_time_utc)) AS duration_sec
- Port-based filtering: WHERE destination_port_s = '80' or WHERE destination_port_s LIKE '%53%'
- Attack category grouping: Use CASE or LIKE patterns on event_type prefix (e.g. 'c2%', 'phishing%', 'scan%', 'ddos%')`;
