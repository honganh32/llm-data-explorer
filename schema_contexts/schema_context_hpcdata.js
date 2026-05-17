// HPCData schema — sourced from the live PostgreSQL database.
// Edit this file to update the AI's schema knowledge; the HTML loads it at startup.
// Prompt caching (cache_control: ephemeral) is applied in the HTML so this block
// is only billed once per cache TTL (~5 min), not on every message.
//
// Naming conventions:
//   schema : hpc
//   tables : job_details, jobs, nodes
//   columns: snake_case (job_id, user_name, submit_time, power_per_core …)
//
// IMPORTANT: All timestamp columns (submit_time, start_time, end_time, eligible_time,
// preempt_time, suspend_time, resize_time, deadline, and the "time" columns in hpc.jobs
// and hpc.nodes) are stored as Unix epoch seconds (bigint).
// Always wrap them with to_timestamp() for human-readable output or date filtering.
// Example: to_timestamp(submit_time) AT TIME ZONE 'UTC'

const HPCDATA_SCHEMA_CONTEXT = `## Schema — HPCData (PostgreSQL)

IMPORTANT: Always use schema-qualified names exactly as shown below.
Example: hpc.job_details, hpc.jobs, hpc.nodes

---

### hpc.job_details
Slurm scheduler records — one row per job submission. Row count: ~293 rows.
- job_id (bigint) — Slurm job ID; join key to hpc.jobs
- array_job_id (bigint, nullable) — parent job ID for array jobs
- array_task_id (bigint, nullable) — task index within an array job
- name (text) — job name as submitted by the user
- job_state (text) — JSON array string, e.g. '["COMPLETED"]', '["FAILED"]', '["CANCELLED"]'
  Values: ["COMPLETED"], ["FAILED"], ["CANCELLED"]
  Filter with: job_state LIKE '%COMPLETED%'  OR  job_state::jsonb->>0 = 'COMPLETED'
- user_id (bigint), user_name (text) — submitting user (e.g. afaiyaz, bantran, chizhou …)
- group_id (bigint) — Unix group ID
- cluster (text) — always "repacss"
- partition (text) — always "h100" (NVIDIA H100 GPU partition)
- command (text, nullable) — full command line of the job script
- current_working_directory (text, nullable) — working directory at submission time
- batch_flag (boolean) — true = batch job (sbatch), false = interactive
- batch_host (text, nullable) — node that ran the batch script
- nodes (text, nullable) — node list string (e.g. "rpg-93-[1-4]")
- node_count (bigint) — number of nodes allocated
- cpus (bigint) — total CPU cores allocated
- tasks (bigint, nullable) — total MPI tasks
- tasks_per_node (bigint, nullable) — MPI tasks per node
- cpus_per_task (bigint, nullable) — CPUs per MPI task
- memory_per_node (bigint, nullable) — requested RAM per node in MB
- memory_per_cpu (bigint, nullable) — requested RAM per CPU in MB
- priority (bigint, nullable) — Slurm scheduler priority
- time_limit (bigint, nullable) — wall-clock time limit in seconds
- deadline (bigint, nullable) — Unix epoch deadline timestamp
- submit_time (bigint) — Unix epoch submission timestamp → use to_timestamp(submit_time)
- eligible_time (bigint) — Unix epoch time job became eligible to run
- start_time (bigint) — Unix epoch start timestamp → use to_timestamp(start_time)
- end_time (bigint) — Unix epoch end timestamp → use to_timestamp(end_time)
- preempt_time (bigint, nullable), suspend_time (bigint, nullable), resize_time (bigint, nullable)
- restart_cnt (bigint) — number of times the job was restarted
- exit_code (bigint) — job exit code (0 = success)
- derived_exit_code (bigint) — highest exit code of any step
- Date range: 2025-06-15 to 2026-05-02

---

### hpc.jobs
Per-job power and resource time-series snapshots. Row count: ~124 rows.
- time (bigint) — Unix epoch snapshot timestamp → use to_timestamp(time)
- job_id (bigint, FK → hpc.job_details.job_id)
- data (text) — JSON array of per-node breakdowns:
  e.g. '[{"node": "rpg-93-3", "power": 718, "cores": 1}]'
  Parse with: data::jsonb, jsonb_array_elements(data::jsonb)
- power (double precision) — total job power consumption in Watts
- cores (bigint) — total CPU cores in use
- power_per_core (double precision) — Watts per core
- memory_per_core (bigint) — MB of RAM per core
- memory_used (bigint) — total RAM used in MB
- Date range: 2025-06-16 01:00 to 03:00 UTC

---

### hpc.nodes
Per-node hardware monitoring time-series. Row count: ~200 rows.
- time (bigint) — Unix epoch snapshot timestamp → use to_timestamp(time)
- node (text) — node hostname; values: rpg-93-1, rpg-93-2, …, rpg-93-8 (8 nodes total)
- used_cores (double precision) — CPU cores currently allocated
- jobs (text) — JSON array of job IDs running on this node, e.g. '[660]' or '[]'
- cores (text) — JSON array of core counts per running job
- cpu_usage (double precision) — total CPU utilisation (0.0–100.0 %)
- memory_usage (double precision) — RAM utilisation percentage
- system_power_consumption (double precision) — total node power draw in Watts
- gpu_usage_labels (text) — JSON array of GPU labels, e.g. '["GPU-0","GPU-1","GPU-2","GPU-3"]'
- gpu_usage (text) — JSON array of GPU utilisation %, one per label
- gpu_power_consumption_labels (text) — JSON array of GPU power labels
- gpu_power_consumption (text) — JSON array of GPU power values in Watts
- gpu_memory_usage_labels (text) — JSON array of GPU memory labels
- gpu_memory_usage (text) — JSON array of GPU memory usage values
- temperature_labels (text) — JSON array, e.g. '["CPU-0","CPU-1","GPU-0","GPU-1","GPU-2","GPU-3"]'
- temperature (text) — JSON array of temperatures in °C, one per label
- cpu_power_consumption_labels (text) — JSON array, e.g. '["CPU-0","CPU-1"]'
- cpu_power_consumption (text) — JSON array of per-CPU-socket power in Watts
- dram_usage (text, nullable) — DRAM utilisation
- dram_power_consumption_labels (text), dram_power_consumption (text) — DRAM power breakdown
- Date range: 2025-06-16 01:00 to 03:00 UTC

---

## Key Relationships
- hpc.jobs.job_id → hpc.job_details.job_id (join for job metadata + resource metrics)
- hpc.nodes.node appears inside hpc.jobs.data JSON (per-node power breakdown per job)
- hpc.nodes.jobs JSON array contains job_ids that map to hpc.job_details.job_id

---

## Working with JSON / Array Columns
All array-typed columns (jobs, cores, gpu_usage, temperature, cpu_power_consumption, etc.)
are stored as JSON text strings. Use ::jsonb to parse them:

-- Unnest per-node job data from hpc.jobs:
SELECT j.job_id, n->>'node' AS node, (n->>'power')::numeric AS power_w
FROM hpc.jobs j, jsonb_array_elements(j.data::jsonb) n;

-- Unnest GPU usage from hpc.nodes:
SELECT n.node, to_timestamp(n.time) AS ts,
       label, usage
FROM hpc.nodes n,
     jsonb_array_elements_text(n.gpu_usage_labels::jsonb) WITH ORDINALITY AS l(label, idx),
     jsonb_array_elements_text(n.gpu_usage::jsonb)        WITH ORDINALITY AS u(usage, idx2)
WHERE l.idx = u.idx2;

-- Filter by job state:
SELECT * FROM hpc.job_details WHERE job_state LIKE '%COMPLETED%';

-- Compute job wall-clock duration:
SELECT job_id, user_name,
       to_timestamp(start_time) AS started,
       to_timestamp(end_time)   AS ended,
       (end_time - start_time) / 3600.0 AS duration_hours
FROM hpc.job_details
WHERE start_time IS NOT NULL AND end_time IS NOT NULL;

---

## Common Query Patterns
- Job counts by state: GROUP BY job_state::jsonb->>0
- User activity: GROUP BY user_name ORDER BY COUNT(*) DESC
- Node utilisation over time: SELECT to_timestamp(time), node, cpu_usage, memory_usage FROM hpc.nodes
- Power analysis: JOIN hpc.jobs WITH hpc.job_details ON job_id for user+power correlation
- GPU utilisation: Unnest gpu_usage JSON from hpc.nodes, group by label and time
- Job queue wait time: (start_time - submit_time) AS queue_wait_seconds
- Time conversions: ALWAYS use to_timestamp() on submit_time, start_time, end_time, time columns`;
