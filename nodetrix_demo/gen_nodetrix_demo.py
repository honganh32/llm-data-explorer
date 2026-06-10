#!/usr/bin/env python3
"""
Pre-aggregate the Network90Mins flow shards into a single JSON the NodeTrix demo
page can render directly in the browser.

Instead of slicing the capture into one-minute buckets, this builds ONE graph for
the whole 90-minute window:
  1. sum packet `count` per (src_ip, dst_ip) pair across the entire capture,
  2. drop the low-activity pairs (the long tail of connections seen only a few
     times in the raw data),
  3. keep the TOP_EDGES busiest pairs and emit them as { source, target, value },
     where source/target are indices into a de-duplicated node list.

The data is a hub-and-spoke topology: a few thousand IPs each talk to many
partners, but the high-degree hubs rarely talk to each other. Filtering by node
degree therefore destroys almost every connection, so we filter by edge weight
(raw packet count) instead -- that preserves the busiest part of the network.

The browser can't read 11M-row parquet, so this runs once and writes data.json.
NodeTrix detects communities client-side, so we only need nodes + links.

Usage:
    python nodetrix_demo/gen_nodetrix_demo.py
    python nodetrix_demo/gen_nodetrix_demo.py --src <dir> --out <file> --top-edges 12000
    python nodetrix_demo/gen_nodetrix_demo.py --min-count 685   # threshold instead of top-N
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

DEFAULT_SRC = r"E:\AdventureWorksCSV\NETWORK_90MINS_BIN_DATA\decoded_set1_90min_packets\resolutions\minutes"


def aggregate(src_dir: Path):
    """Sum packet count per (src_ip, dst_ip) pair across the whole capture."""
    index = json.loads((src_dir / "index.json").read_text())
    cols = ["src_ip", "dst_ip", "count"]

    parts = []
    for chunk in index["chunks"]:
        path = src_dir / chunk["file"]
        print(f"  reading {chunk['file']} ({chunk['count']:,} rows) ...")
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(batch_size=1_000_000, columns=cols):
            df = batch.to_pandas()
            df = df[df["src_ip"] != df["dst_ip"]]  # drop self-loops
            parts.append(
                df.groupby(["src_ip", "dst_ip"], as_index=False)["count"].sum()
            )

    print("  combining partial aggregates ...")
    edges = (
        pd.concat(parts, ignore_index=True)
        .groupby(["src_ip", "dst_ip"], as_index=False)["count"]
        .sum()
    )
    return index, edges


def build_graph(edges: pd.DataFrame, top_edges: int, min_count: int):
    """Keep the busiest connections, then map to a node-indexed graph."""
    total_pairs = len(edges)
    if min_count is not None:
        kept = edges[edges["count"] >= min_count].copy()
    else:
        kept = edges.sort_values("count", ascending=False).head(top_edges).copy()
    kept = kept.sort_values("count", ascending=False).reset_index(drop=True)

    # De-duplicated node list; links reference nodes by index to keep JSON small.
    ips = pd.unique(kept[["src_ip", "dst_ip"]].values.ravel())
    idx = {ip: i for i, ip in enumerate(ips)}
    nodes = [{"name": str(ip)} for ip in ips]
    links = [
        {"source": idx[r.src_ip], "target": idx[r.dst_ip], "value": int(r.count)}
        for r in kept.itertuples()
    ]
    min_kept = int(kept["count"].min()) if len(kept) else 0
    return nodes, links, total_pairs, min_kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=str(Path(__file__).parent / "data.json"))
    ap.add_argument("--top-edges", type=int, default=20000,
                    help="keep the N busiest connections (>= 10000 recommended)")
    ap.add_argument("--min-count", type=int, default=None,
                    help="alternative: keep all connections with packet count >= this")
    args = ap.parse_args()

    src_dir = Path(args.src)
    if not src_dir.exists():
        raise SystemExit(f"Source dir not found: {src_dir}")

    print(f"Aggregating the full capture from {src_dir} ...")
    index, edges = aggregate(src_dir)
    nodes, links, total_pairs, min_kept = build_graph(
        edges, args.top_edges, args.min_count
    )

    start_us = index["time_range"]["start"]
    end_us = index["time_range"]["end"]
    span_min = (end_us - start_us) / 60_000_000
    label = (
        datetime.fromtimestamp(start_us / 1e6, tz=timezone.utc).strftime("%H:%M")
        + "–"
        + datetime.fromtimestamp(end_us / 1e6, tz=timezone.utc).strftime("%H:%M UTC")
    )

    out = {
        "title": "Network90Mins — busiest IP-to-IP connections (full capture)",
        "window": label,
        "span_minutes": round(span_min, 1),
        "total_pairs": total_pairs,
        "min_count": min_kept,
        "n_nodes": len(nodes),
        "n_links": len(links),
        "nodes": nodes,
        "links": links,
    }
    out_path = Path(args.out)
    out_path.write_text(json.dumps(out), encoding="utf-8")
    print(f"\nWrote {out_path}")
    print(f"  {len(nodes):,} IPs, {len(links):,} connections "
          f"(kept pairs with packet count >= {min_kept:,} of {total_pairs:,} total), "
          f"{out_path.stat().st_size/1024:.0f} KB")


if __name__ == "__main__":
    main()
