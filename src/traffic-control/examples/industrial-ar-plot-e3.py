#!/usr/bin/env python3
"""Create application and network metric plots for the E3 run."""

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
    parser.add_argument("--results", default="results/industrial-ar", help="Directory containing industrial-e3 output files")
    args = parser.parse_args()
    root = Path(args.results)
    prefix = root / "industrial-e3"
    apps = read_csv(str(prefix) + ".applications.csv")
    metrics = {row["application"]: row for row in apps}
    network = read_csv(str(prefix) + ".network.csv")[0]

    # Throughput and demand.
    fig, ax = plt.subplots(figsize=(9, 5))
    x = list(range(4))
    offered = [float(metrics[a]["offered_mbps"]) for a in APPS]
    received = [float(metrics[a]["throughput_mbps"]) for a in APPS]
    width = 0.36
    b1 = ax.bar([i - width / 2 for i in x], offered, width, label="Offered", color="#B9C8D8")
    b2 = ax.bar([i + width / 2 for i in x], received, width, label="Received", color=COLORS)
    ax.bar_label(b1, fmt="%.2f", padding=2, fontsize=8)
    ax.bar_label(b2, fmt="%.2f", padding=2, fontsize=8)
    ax.set_xticks(x, LABELS, rotation=15, ha="right")
    ax.set_ylabel("Rate (Mbps)")
    ax.set_title("E3 application throughput")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    save(fig, root / "e3-throughput.png")

    # Mean and tail delay.
    fig, ax = plt.subplots(figsize=(10, 5))
    width = 0.24
    for j, (field, title, color) in enumerate((
        ("mean_delay_ms", "Mean", "#9ECAE1"),
        ("p95_delay_ms", "p95", "#4292C6"),
        ("p99_delay_ms", "p99", "#084594"),
    )):
        values = [float(metrics[a][field]) for a in APPS]
        bars = ax.bar([i + (j - 1) * width for i in x], values, width, label=title, color=color)
        ax.bar_label(bars, fmt="%.0f", padding=2, fontsize=8)
    ax.set_xticks(x, LABELS, rotation=15, ha="right")
    ax.set_ylabel("Delay (ms)")
    ax.set_title("E3 end-to-end delay")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(title="Statistic")
    save(fig, root / "e3-delay.png")

    # Jitter and loss, with zero-loss values labeled so they remain visible.
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    jitter = [float(metrics[a]["jitter_ms"]) for a in APPS]
    bars = axes[0].bar(LABELS, jitter, color=COLORS)
    axes[0].bar_label(bars, fmt="%.3f", padding=3, fontsize=8)
    axes[0].set_ylabel("Average jitter (ms)")
    axes[0].set_title("FlowMonitor jitter")
    axes[0].tick_params(axis="x", rotation=25)
    losses = [100 * float(metrics[a]["loss_ratio"]) for a in APPS]
    bars = axes[1].bar(LABELS, losses, color=COLORS)
    axes[1].bar_label(bars, labels=[f"{v:.2f}%" for v in losses], padding=3, fontsize=8)
    axes[1].set_ylim(0, 1)
    axes[1].set_ylabel("Lost packets / transmitted packets (%)")
    axes[1].set_title("Packet loss")
    axes[1].tick_params(axis="x", rotation=25)
    for ax in axes:
        ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    save(fig, root / "e3-jitter-loss.png")

    # Network marking and application satisfaction.
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    mark = 100 * float(network["mark_ratio"])
    bars = axes[0].bar(["DualPI2 aggregate"], [mark], color="#E45756")
    axes[0].bar_label(bars, labels=[f"{mark:.2f}%"], padding=3)
    axes[0].set_ylim(0, max(1.0, mark * 1.2))
    axes[0].set_ylabel("Marked / enqueued packets (%)")
    axes[0].set_title("ECN marking")
    sat = [float(metrics[a]["utility_satisfaction"]) * 100 for a in APPS]
    bars = axes[1].bar(LABELS, sat, color=COLORS)
    axes[1].bar_label(bars, fmt="%.1f%%", padding=3, fontsize=8)
    axes[1].set_ylim(0, 110)
    axes[1].set_ylabel("min(received / offered, 1) (%)")
    axes[1].set_title("Application satisfaction")
    axes[1].tick_params(axis="x", rotation=25)
    for ax in axes:
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle(f"E3 network marking and utility satisfaction (weighted score {float(network['weighted_utility_satisfaction']):.3f})")
    fig.tight_layout()
    save(fig, root / "e3-ecn-satisfaction.png")

    # Utility values change with the four activity phases.
    profiles = {
        "Remote video": [0.9, 0.4, 0.6, 0.9],
        "3D instructions": [0.6, 0.9, 0.5, 0.6],
        "Sensors": [0.5, 0.6, 0.9, 0.5],
        "Maintenance logs": [0.2, 0.2, 0.2, 0.2],
    }
    times = [0, 30, 60, 80, 100]
    fig, ax = plt.subplots(figsize=(10, 5))
    for i, (label, values) in enumerate(profiles.items()):
        ax.step(times, values + [values[-1]], where="post", color=COLORS[i], linewidth=2, label=label)
    ax.set_xticks(times)
    ax.set_ylim(0, 1.0)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Application utility")
    ax.set_title("E3 utility schedule")
    ax.grid(alpha=0.25)
    ax.legend(ncol=2)
    save(fig, root / "e3-utility-schedule.png")

    # Congestion window time series, one panel per connection.
    cwnd = read_csv(str(prefix) + ".cwnd.csv")
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    for i, (ax, app, label) in enumerate(zip(axes, APPS, LABELS)):
        series = [row for row in cwnd if row["application"] == app]
        times = [float(row["time_s"]) for row in series]
        values = [float(row["new_cwnd_bytes"]) / 1024 for row in series]
        ax.plot(times, values, linewidth=0.55, color=COLORS[i])
        for transition in (30, 60, 80):
            ax.axvline(transition, color="#777777", linewidth=0.8, linestyle="--")
        ax.set_ylabel(label + "\ncwnd (KiB)")
        ax.grid(alpha=0.2)
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle("E3 TCP congestion windows and utility transitions")
    fig.tight_layout()
    save(fig, root / "e3-cwnd.png")

    # Queue occupancy and L4S sojourn distribution.
    queue = read_csv(str(prefix) + ".queue.csv")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].plot([float(row["time_s"]) for row in queue],
                 [float(row["queue_bytes"]) / 1000 for row in queue],
                 color="#4C78A8", linewidth=0.8)
    axes[0].set_xlabel("Time (s)")
    axes[0].set_ylabel("Aggregate queue (kB)")
    axes[0].set_title("DualPI2 queue occupancy")
    axes[0].grid(alpha=0.25)
    sojourn = read_csv(str(prefix) + ".sojourn.csv")
    l4s = [float(row["sojourn_ms"]) for row in sojourn if row["queue"] == "l4s"]
    classic = [float(row["sojourn_ms"]) for row in sojourn if row["queue"] == "classic"]
    zero_fraction = 100 * sum(value == 0 for value in l4s) / len(l4s) if l4s else 0
    positive_l4s = [value for value in l4s if value > 0]
    if positive_l4s:
        axes[1].hist(positive_l4s, bins=30,
                     range=(0, max(1, max(positive_l4s))), density=True,
                     alpha=0.75, color="#54A24B", label="L4S (>0 ms)")
    else:
        axes[1].text(0.5, 0.5, "No positive L4S sojourn samples",
                     transform=axes[1].transAxes, ha="center", va="center")
    if classic:
        positive_classic = [value for value in classic if value > 0]
        if positive_classic:
            axes[1].hist(positive_classic, bins=30,
                         range=(0, max(1, max(positive_classic))), density=True,
                         alpha=0.5, color="#F58518", label="Classic (>0 ms)")
        else:
            axes[1].text(0.5, 0.85, "Classic samples are absent or zero",
                         transform=axes[1].transAxes, ha="center", va="center")
    else:
        axes[1].text(0.5, 0.8, "No Classic samples in E3", transform=axes[1].transAxes,
                     ha="center", va="center")
    axes[1].set_xlabel("Sojourn time (ms)")
    axes[1].set_ylabel("Probability density (positive samples)")
    axes[1].set_title(f"Queue sojourn; {zero_fraction:.1f}% of L4S samples are zero")
    axes[1].grid(alpha=0.25)
    axes[1].legend()
    fig.tight_layout()
    save(fig, root / "e3-queue-sojourn.png")


if __name__ == "__main__":
    main()
