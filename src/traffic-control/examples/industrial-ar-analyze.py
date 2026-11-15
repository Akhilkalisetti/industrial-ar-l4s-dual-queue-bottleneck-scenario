#!/usr/bin/env python3
"""Combine Industrial AR E1/E2/E3 CSV measurements into one comparison CSV."""

import argparse
import csv
import math
from pathlib import Path


def read_rows(path):
    with Path(path).open(newline="") as stream:
        return list(csv.DictReader(stream))


def percentile(values, quantile):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
    return ordered[index]


def queue_metrics(prefix):
    queue_rows = read_rows(str(prefix) + ".queue.csv")
    queue = [float(row["queue_bytes"]) for row in queue_rows]
    sojourn_rows = read_rows(str(prefix) + ".sojourn.csv")
    metrics = {
        "queue_avg_bytes": sum(queue) / len(queue) if queue else 0.0,
        "queue_p95_bytes": percentile(queue, 0.95),
        "queue_p99_bytes": percentile(queue, 0.99),
        "queue_max_bytes": max(queue, default=0.0),
    }
    for queue_name in ("classic", "l4s"):
        values = [float(row["sojourn_ms"]) for row in sojourn_rows if row["queue"] == queue_name]
        metrics[queue_name + "_sojourn_avg_ms"] = sum(values) / len(values) if values else 0.0
        metrics[queue_name + "_sojourn_p95_ms"] = percentile(values, 0.95)
        metrics[queue_name + "_sojourn_p99_ms"] = percentile(values, 0.99)
        metrics[queue_name + "_sojourn_samples"] = len(values)
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e1", required=True, help="E1 output prefix")
    parser.add_argument("--e2", required=True, help="E2 output prefix")
    parser.add_argument("--e3", required=True, help="E3 output prefix")
    parser.add_argument("--output", default="industrial-ar-comparison.csv")
    args = parser.parse_args()

    rows = []
    for experiment, prefix in (("E1", args.e1), ("E2", args.e2), ("E3", args.e3)):
        prefix = Path(prefix)
        app_rows = read_rows(str(prefix) + ".applications.csv")
        network = read_rows(str(prefix) + ".network.csv")[0]
        queues = queue_metrics(prefix)
        for app in app_rows:
            rows.append({
                "experiment": experiment,
                "application": app["application"],
                "offered_mbps": app["offered_mbps"],
                "throughput_mbps": app["throughput_mbps"],
                "mean_delay_ms": app["mean_delay_ms"],
                "p95_delay_ms": app["p95_delay_ms"],
                "p99_delay_ms": app["p99_delay_ms"],
                "jitter_ms": app["jitter_ms"],
                "tx_packets": app["tx_packets"],
                "rx_packets": app["rx_packets"],
                "lost_packets": app["lost_packets"],
                "loss_ratio": app["loss_ratio"],
                "mean_control_utility": app["mean_control_utility"],
                "mean_target_utility": app["mean_target_utility"],
                "utility_satisfaction": app["utility_satisfaction"],
                "network_mark_ratio": network["mark_ratio"],
                "network_dropped_packets": network["dropped_packets"],
                "weighted_utility_satisfaction": network["weighted_utility_satisfaction"],
                **queues,
            })

    fields = list(rows[0].keys()) if rows else []
    with Path(args.output).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print("Wrote", args.output)
    print("experiment,application,throughput_mbps,p95_ms,p99_ms,loss_ratio,utility_satisfaction,mark_ratio,queue_p95_bytes,l4s_sojourn_p99_ms")
    for row in rows:
        print("{experiment},{application},{throughput_mbps},{p95_delay_ms},{p99_delay_ms},{loss_ratio},{utility_satisfaction},{network_mark_ratio},{queue_p95_bytes},{l4s_sojourn_p99_ms}".format(**row))


if __name__ == "__main__":
    main()
