#!/usr/bin/env python3
"""Organize industrial AR outputs into E1, E2, and E3 directories."""

import argparse
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default="results/industrial-ar")
    args = parser.parse_args()
    root = Path(args.results)

    for experiment in ("E1", "E2", "E3"):
        source_prefix = root / f"industrial-{experiment.lower()}"
        destination = root / experiment
        destination.mkdir(parents=True, exist_ok=True)
        for suffix in (".applications.csv", ".network.csv", ".queue.csv",
                       ".sojourn.csv", ".cwnd.csv", ".flowmon", ".log"):
            source = Path(str(source_prefix) + suffix)
            if not source.exists():
                raise FileNotFoundError(f"Missing {source}")
            target_name = {
                ".applications.csv": "applications.csv",
                ".network.csv": "network.csv",
                ".queue.csv": "queue.csv",
                ".sojourn.csv": "sojourn.csv",
                ".cwnd.csv": "cwnd.csv",
                ".flowmon": "flowmon",
                ".log": "run.log",
            }[suffix]
            shutil.copy2(source, destination / target_name)
        print(f"Organized {experiment} in {destination}")


if __name__ == "__main__":
    main()
