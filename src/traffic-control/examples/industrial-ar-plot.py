#!/usr/bin/env python3
"""Create PNG figures from industrial-ar-analyze.py and simulation traces."""

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


COLORS = {"E1": "#4C78A8", "E2": "#F58518", "E3": "#54A24B"}
APPS = ["video", "instructions", "sensors", "logs"]
APP_LABELS = ["Remote video", "3D instructions", "Sensors", "Maintenance logs"]
EXPERIMENTS = ["E1", "E2", "E3"]


def rows(path):
    with Path(path).open(newline="") as stream:
        return list(csv.DictReader(stream))


def save(fig, path):
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("Wrote", path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default="results/industrial-ar", help="Directory containing the experiment CSV files")
    args = parser.parse_args()
    root = Path(args.results)
    root.mkdir(parents=True, exist_ok=True)
    comparison = rows(root / "comparison.csv")
    indexed = {(row["experiment"], row["application"]): row for row in comparison}

    # Per-application goodput.
    fig, ax = plt.subplots(figsize=(10, 5.5))
    x = list(range(len(APPS)))
    width = 0.24
    for j, experiment in enumerate(EXPERIMENTS):
        values = [float(indexed[(experiment, app)]["throughput_mbps"]) for app in APPS]
        bars = ax.bar([i + (j - 1) * width for i in x], values, width,
                      label=experiment, color=COLORS[experiment])
        ax.bar_label(bars, fmt="%.2f", padding=2, fontsize=8)
    ax.set_xticks(x, APP_LABELS)
    ax.set_ylabel("Throughput (Mbps)")
    ax.set_title("Per-application throughput")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(title="Experiment")
    save(fig, root / "throughput.png")

    # Delay percentiles by application; separate panels keep the scales readable.
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=False)
    for ax, field, title in zip(axes,
                                ("mean_delay_ms", "p95_delay_ms", "p99_delay_ms"),
                                ("Mean delay", "95th percentile delay", "99th percentile delay")):
        for j, experiment in enumerate(EXPERIMENTS):
            values = [float(indexed[(experiment, app)][field]) for app in APPS]
            bars = ax.bar([i + (j - 1) * width for i in x], values, width,
                          label=experiment, color=COLORS[experiment])
            ax.bar_label(bars, fmt="%.0f", padding=2, fontsize=7, rotation=90)
        ax.set_xticks(x, ["Video", "3D", "Sensor", "Logs"], rotation=25, ha="right")
        ax.set_title(title)
        ax.set_ylabel("Delay (ms)")
        ax.grid(axis="y", alpha=0.25)
    axes[-1].legend(title="Experiment")
    fig.suptitle("End-to-end delay by application")
    fig.tight_layout()
    save(fig, root / "delay-percentiles.png")

    # DualPI2 aggregate queue occupancy.
    fig, ax = plt.subplots(figsize=(11, 5))
    for experiment in EXPERIMENTS:
        series = rows(root / f"industrial-{experiment.lower()}.queue.csv")
        times = [float(row["time_s"]) for row in series]
        sizes = [float(row["queue_bytes"]) / 1000 for row in series]
        ax.plot(times, sizes, color=COLORS[experiment], linewidth=0.8, label=experiment)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Queue occupancy (kB)")
    ax.set_title("DualPI2 aggregate queue occupancy")
    ax.grid(alpha=0.25)
    ax.legend(title="Experiment")
    save(fig, root / "queue-occupancy.png")

    # E3 cwnd over time, with application utility transition times.
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    cwnd = rows(root / "industrial-e3.cwnd.csv")
    for ax, app, label in zip(axes, APPS, APP_LABELS):
        series = [row for row in cwnd if row["application"] == app]
        times = [float(row["time_s"]) for row in series]
        values = [float(row["new_cwnd_bytes"]) / 1024 for row in series]
        ax.plot(times, values, linewidth=0.55, color=COLORS["E3"])
        for transition in (30, 60, 80):
            ax.axvline(transition, color="#777777", linewidth=0.8, linestyle="--")
        ax.set_ylabel(label + "\ncwnd (KiB)")
        ax.grid(alpha=0.2)
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle("E3 congestion-window response and utility transitions")
    fig.tight_layout()
    save(fig, root / "e3-cwnd.png")

    # Network-level marking and common-schedule utility satisfaction.
    net = {row["experiment"]: row for row in
           (rows(root / f"industrial-{e.lower()}.network.csv")[0] for e in EXPERIMENTS)}
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.5))
    for ax, field, title, scale in (
        (axes[0], "mark_ratio", "ECN marking ratio", 100.0),
        (axes[1], "weighted_utility_satisfaction", "Weighted utility satisfaction", 100.0),
    ):
        vals = [float(net[e][field]) * scale for e in EXPERIMENTS]
        bars = ax.bar(EXPERIMENTS, vals, color=[COLORS[e] for e in EXPERIMENTS])
        ax.bar_label(bars, fmt="%.1f%%", padding=3)
        ax.set_title(title)
        ax.set_ylabel("Percent")
        ax.set_ylim(0, max(vals) * 1.18 if vals else 1)
        ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    save(fig, root / "network-metrics.png")


if __name__ == "__main__":
    main()
