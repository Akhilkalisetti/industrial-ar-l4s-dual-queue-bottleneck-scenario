#!/usr/bin/env python3
"""Create separate metric plots for one industrial AR experiment."""

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


APPS = ["video", "instructions", "sensors", "logs"]
LABELS = ["Remote video", "3D instructions", "Sensors", "Maintenance logs"]
COLORS = ["#4C78A8", "#F58518", "#54A24B", "#B279A2"]


def read_csv(path):
    with Path(path).open(newline="") as stream:
        return list(csv.DictReader(stream))


def save(fig, path):
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("Wrote", path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True,
                        help="Directory containing applications.csv and trace CSV files")
    parser.add_argument("--experiment", required=True, choices=("E1", "E2", "E3"))
    args = parser.parse_args()
    root = Path(args.results)
    experiment = args.experiment
    metrics = {row["application"]: row for row in read_csv(root / "applications.csv")}
    network = read_csv(root / "network.csv")[0]
    x = list(range(len(APPS)))

    fig, ax = plt.subplots(figsize=(9, 5))
    width = 0.36
    offered = [float(metrics[a]["offered_mbps"]) for a in APPS]
    received = [float(metrics[a]["throughput_mbps"]) for a in APPS]
    ax.bar([i - width / 2 for i in x], offered, width, label="Offered", color="#B9C8D8")
    ax.bar([i + width / 2 for i in x], received, width, label="Received", color=COLORS)
    ax.set_xticks(x, LABELS, rotation=15, ha="right")
    ax.set_ylabel("Rate (Mbps)")
    ax.set_title(f"{experiment} application throughput")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    save(fig, root / "throughput.png")

    fig, ax = plt.subplots(figsize=(10, 5))
    width = 0.24
    for j, (field, title, color) in enumerate((
        ("mean_delay_ms", "Mean", "#9ECAE1"),
        ("p95_delay_ms", "p95", "#4292C6"),
        ("p99_delay_ms", "p99", "#084594"),
    )):
        values = [float(metrics[a][field]) for a in APPS]
        ax.bar([i + (j - 1) * width for i in x], values, width,
               label=title, color=color)
    ax.set_xticks(x, LABELS, rotation=15, ha="right")
    ax.set_ylabel("Delay (ms)")
    ax.set_title(f"{experiment} end-to-end delay")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(title="Statistic")
    save(fig, root / "delay.png")

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    jitter = [float(metrics[a]["jitter_ms"]) for a in APPS]
    losses = [100 * float(metrics[a]["loss_ratio"]) for a in APPS]
    axes[0].bar(LABELS, jitter, color=COLORS)
    axes[0].set_ylabel("Average jitter (ms)")
    axes[0].set_title("FlowMonitor jitter")
    axes[1].bar(LABELS, losses, color=COLORS)
    axes[1].set_ylim(0, max(1.0, max(losses, default=0) * 1.2))
    axes[1].set_ylabel("Packet loss (%)")
    axes[1].set_title("Packet loss")
    for ax in axes:
        ax.tick_params(axis="x", rotation=25)
        ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    save(fig, root / "jitter-loss.png")

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    mark = 100 * float(network["mark_ratio"])
    axes[0].bar(["DualPI2 aggregate"], [mark], color="#E45756")
    axes[0].set_ylim(0, max(1.0, mark * 1.2))
    axes[0].set_ylabel("Marked / enqueued packets (%)")
    axes[0].set_title("ECN marking")
    satisfaction = [100 * float(metrics[a]["utility_satisfaction"]) for a in APPS]
    axes[1].bar(LABELS, satisfaction, color=COLORS)
    axes[1].set_ylim(0, 110)
    axes[1].set_ylabel("Satisfaction (%)")
    axes[1].set_title("Application satisfaction")
    for ax in axes:
        ax.tick_params(axis="x", rotation=25)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle(f"{experiment} network metrics "
                 f"(weighted score {float(network['weighted_utility_satisfaction']):.3f})")
    fig.tight_layout()
    save(fig, root / "network-metrics.png")

    queue = read_csv(root / "queue.csv")
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot([float(row["time_s"]) for row in queue],
            [float(row["queue_bytes"]) / 1000 for row in queue],
            color="#4C78A8", linewidth=0.8)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Aggregate queue (kB)")
    ax.set_title(f"{experiment} DualPI2 queue occupancy")
    ax.grid(alpha=0.25)
    save(fig, root / "queue-occupancy.png")

    sojourn = read_csv(root / "sojourn.csv")
    l4s = [float(row["sojourn_ms"]) for row in sojourn if row["queue"] == "l4s"]
    classic = [float(row["sojourn_ms"]) for row in sojourn if row["queue"] == "classic"]
    fig, ax = plt.subplots(figsize=(8, 5))
    # A large number of exact zero-sojourn samples can hide the non-zero tail.
    # Plot non-zero samples separately and report the zero fraction in the title.
    zero_fraction = 100 * sum(value == 0 for value in l4s) / len(l4s) if l4s else 0
    positive_l4s = [value for value in l4s if value > 0]
    if positive_l4s:
        ax.hist(positive_l4s, bins=30, range=(0, max(1, max(positive_l4s))),
                density=True, alpha=0.75, color="#54A24B", label="L4S (>0 ms)")
    else:
        ax.text(0.5, 0.5, "No positive L4S sojourn samples", transform=ax.transAxes,
                ha="center", va="center")
    if classic:
        positive_classic = [value for value in classic if value > 0]
        if positive_classic:
            ax.hist(positive_classic, bins=30,
                    range=(0, max(1, max(positive_classic))), density=True, alpha=0.5,
                    color="#F58518", label="Classic (>0 ms)")
        else:
            ax.text(0.5, 0.85, "Classic samples are absent or zero",
                    transform=ax.transAxes, ha="center", va="center")
    ax.set_xlabel("Sojourn time (ms)")
    ax.set_ylabel("Probability density (positive samples)")
    ax.set_title(f"{experiment} queue sojourn; {zero_fraction:.1f}% of L4S samples are zero")
    ax.grid(alpha=0.25)
    ax.legend()
    save(fig, root / "queue-sojourn.png")

    cwnd = read_csv(root / "cwnd.csv")
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    for ax, app, label, color in zip(axes, APPS, LABELS, COLORS):
        series = [row for row in cwnd if row["application"] == app]
        ax.plot([float(row["time_s"]) for row in series],
                [float(row["new_cwnd_bytes"]) / 1024 for row in series],
                linewidth=0.55, color=color)
        if experiment == "E3":
            for transition in (30, 60, 80):
                ax.axvline(transition, color="#777777",
                           linewidth=0.8, linestyle="--")
        ax.set_ylabel(label + "\ncwnd (KiB)")
        ax.grid(alpha=0.2)
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle(f"{experiment} TCP congestion windows")
    fig.tight_layout()
    save(fig, root / "cwnd.png")

    utility_profiles = {
        "E1": ([1.0, 1.0, 1.0, 1.0], [0, 100]),
        "E2": ([0.9, 0.6, 0.5, 0.2], [0, 100]),
        "E3": ([0.9, 0.4, 0.6, 0.9], [0, 30, 60, 80, 100]),
    }
    if experiment == "E3":
        profiles = [
            [0.9, 0.4, 0.6, 0.9],
            [0.6, 0.9, 0.5, 0.6],
            [0.5, 0.6, 0.9, 0.5],
            [0.2, 0.2, 0.2, 0.2],
        ]
        times = [0, 30, 60, 80, 100]
    else:
        values, times = utility_profiles[experiment]
        profiles = [[value] for value in values]
    fig, ax = plt.subplots(figsize=(10, 5))
    for label, values, color in zip(LABELS, profiles, COLORS):
        if len(times) == 2:
            step_values = values + [values[-1]]
        else:
            step_values = values + [values[-1]]
        ax.step(times, step_values, where="post", color=color,
                linewidth=2, label=label)
    ax.set_xticks(times)
    ax.set_ylim(0, 1.0)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Application utility")
    ax.set_title(f"{experiment} utility policy")
    ax.grid(alpha=0.25)
    ax.legend(ncol=2)
    save(fig, root / "utility-policy.png")


if __name__ == "__main__":
    main()
