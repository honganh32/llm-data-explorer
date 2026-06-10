#!/usr/bin/env python3
"""
Pre-aggregate the minute-binned Network90Mins flow shards into a small JSON the
NodeTrix demo page can render directly in the browser.

For every one-minute bin we:
  1. sum packet `count` per (src_ip, dst_ip) pair,
  2. keep only the TOP_K most active IPs in that minute (by total packets),
  3. emit the edges among those IPs as { source, target, value }.

The browser can't read 11M-row parquet, so this runs once and writes data.json.
NodeTrix detects communities client-side, so we only need nodes + links.

Usage:
    python nodetrix_demo/gen_nodetrix_demo.py
    python nodetrix_demo/gen_nodetrix_demo.py --src <dir> --out <file> --topk 40
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

DEFAULT_SRC = r"E:\AdventureWorksCSV\NETWORK_90MINS_BIN_DATA\decoded_set1_90min_packets\resolutions\minutes"
BIN_US = 60_000_000  # one minute in microseconds


def aggregate(src_dir: Path, top_k: int):
    index = json.loads((src_dir / "index.json").read_text())
    start_us = index["time_range"]["start"]
    cols = ["timestamp", "src_ip", "dst_ip", "count"]

    parts = []
    for chunk in index["chunks"]:
        path = src_dir / chunk["file"]
        print(f"  reading {chunk['file']} ({chunk['count']:,} rows) ...")
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(batch_size=500_000, columns=cols):
            df = batch.to_pandas()
            df = df[df["src_ip"] != df["dst_ip"]]  # drop self-loops
            df["m"] = ((df["timestamp"] - start_us) // BIN_US).astype("int32")
            parts.append(
                df.groupby(["m", "src_ip", "dst_ip"], as_index=False)["count"].sum()
            )

    print("  combining partial aggregates ...")
    edges = (
        pd.concat(parts, ignore_index=True)
        .groupby(["m", "src_ip", "dst_ip"], as_index=False)["count"]
        .sum()
    )

    # Per-minute IP activity = packets sent + received.
    out_act = edges.groupby(["m", "src_ip"])["count"].sum().rename_axis(["m", "ip"])
    in_act = edges.groupby(["m", "dst_ip"])["count"].sum().rename_axis(["m", "ip"])
    activity = out_act.add(in_act, fill_value=0)

    minutes = []
    n_minutes = int(edges["m"].max()) + 1 if len(edges) else 0
    for m in range(n_minutes):
        me = edges[edges["m"] == m]
        if me.empty:
            continue
        top_ips = (
            activity.loc[m].sort_values(ascending=False).head(top_k).index.tolist()
        )
        top_set = set(top_ips)
        kept = me[me["src_ip"].isin(top_set) & me["dst_ip"].isin(top_set)]
        if kept.empty:
            continue
        ts = datetime.fromtimestamp((start_us + m * BIN_US) / 1e6, tz=timezone.utc)
        minutes.append({
            "t": m,
            "label": ts.strftime("%H:%M UTC"),
            "nodes": [{"name": ip} for ip in top_ips if ip in
                      set(kept["src_ip"]).union(kept["dst_ip"])],
            "links": [
                {"source": r.src_ip, "target": r.dst_ip, "value": int(r.count)}
                for r in kept.itertuples()
            ],
        })
    return start_us, minutes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=str(Path(__file__).parent / "data.json"))
    ap.add_argument("--topk", type=int, default=40)
    args = ap.parse_args()

    src_dir = Path(args.src)
    if not src_dir.exists():
        raise SystemExit(f"Source dir not found: {src_dir}")

    print(f"Aggregating minute bins from {src_dir} (top {args.topk} IPs/minute) ...")
    start_us, minutes = aggregate(src_dir, args.topk)

    out = {
        "title": "Network90Mins — minute-binned IP communication (top IPs)",
        "resolution": "minutes",
        "start_us": start_us,
        "topk": args.topk,
        "minutes": minutes,
    }
    out_path = Path(args.out)
    out_path.write_text(json.dumps(out), encoding="utf-8")
    edges = sum(len(m["links"]) for m in minutes)
    print(f"\nWrote {out_path}")
    print(f"  {len(minutes)} minute bins, {edges:,} edges total, "
          f"{out_path.stat().st_size/1024:.0f} KB")


if __name__ == "__main__":
    main()
