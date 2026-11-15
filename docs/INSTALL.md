# Installation and usage

## Requirements

- Linux or another platform supported by this ns-3 checkout
- A C++ compiler and Python 3
- The build dependencies documented in `doc/build.txt`

This project is based on the included ns-3 source tree and its Waf build system.

## Configure and build

From the repository root:

```sh
./waf configure --enable-examples
./waf build
```

## Run the scenarios

Run each experiment into a local output directory (generated outputs are ignored by Git):

```sh
mkdir -p results
./waf --run "industrial-ar-dualq --experiment=E1 --output=results/e1 --pcap=0"
./waf --run "industrial-ar-dualq --experiment=E2 --output=results/e2 --pcap=0"
./waf --run "industrial-ar-dualq --experiment=E3 --output=results/e3 --pcap=0"
```

The experiment definitions, helper commands, and metric descriptions are in [industrial-ar-experiments.md](../src/traffic-control/examples/industrial-ar-experiments.md).

## Analyze and plot generated data

```sh
python3 src/traffic-control/examples/industrial-ar-analyze.py \
  --e1 results/e1 --e2 results/e2 --e3 results/e3 \
  --output results/comparison.csv
```

Plot scripts accept an output directory; run `python3 path/to/script.py --help` for their options. Outputs belong in `results/` and are not intended as committed project resources.

## Notes

The scenario uses the available `TcpDctcp` implementation as an L4S proxy. It does not provide TCP Prague or Accurate ECN. Refer to the experiment documentation before interpreting the model or extending it.
