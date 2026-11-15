# Industrial AR L4S Dual-Queue Bottleneck Scenario

An ns-3 project for modeling industrial augmented-reality traffic over an L4S and Classic dual-queue bottleneck. The repository includes the simulation scenario and reusable analysis and plotting utilities. Generated simulation outputs are not included.

## Project layout

- `src/traffic-control/examples/industrial-ar-dualq.cc` — four-application scenario using DualPI2.
- `src/traffic-control/examples/industrial-ar-experiments.md` — experiment definitions and commands.
- `src/traffic-control/examples/industrial-ar-analyze.py` — combines per-run metrics.
- `src/traffic-control/examples/industrial-ar-organize.py` — arranges generated outputs.
- `src/traffic-control/examples/industrial-ar-plot*.py` — plotting utilities.
- `docs/INSTALL.md` — prerequisites, build, and run instructions.

This is an ns-3 source checkout with project additions. Its L4S congestion control uses the available `TcpDctcp` implementation as a proxy; TCP Prague and Accurate ECN are not included in this checkout.

## Quick start

See [Installation and usage](docs/INSTALL.md) for prerequisites and commands to build and run the E1, E2, and E3 scenarios.

## Documentation

- [Experiment definitions](src/traffic-control/examples/industrial-ar-experiments.md)
- [ns-3 documentation](https://www.nsnam.org/documentation/)

## License

The ns-3 codebase is distributed under GNU GPL version 2. See [LICENSE](LICENSE). Check individual files and upstream ns-3 notices when redistributing modified components.
