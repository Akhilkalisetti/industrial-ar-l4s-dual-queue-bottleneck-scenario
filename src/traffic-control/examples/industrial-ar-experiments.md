# Industrial AR E1/E2/E3 experiments

Build the `industrial-ar-dualq` program, then run one 100-second experiment per mode:

```sh
mkdir -p results
./waf --run "industrial-ar-dualq --experiment=E1 --output=results/e1 --pcap=0"
./waf --run "industrial-ar-dualq --experiment=E2 --output=results/e2 --pcap=0"
./waf --run "industrial-ar-dualq --experiment=E3 --output=results/e3 --pcap=0"
python3 src/traffic-control/examples/industrial-ar-analyze.py \
  --e1 results/e1 --e2 results/e2 --e3 results/e3 \
  --output results/comparison.csv
```

To keep each run separate and create independent metric plots:

```sh
python3 src/traffic-control/examples/industrial-ar-organize.py \
  --results results/industrial-ar
for experiment in E1 E2 E3; do
  python3 src/traffic-control/examples/industrial-ar-plot-single.py \
    --results results/industrial-ar/$experiment --experiment $experiment
done
```

Each experiment directory contains its application, network, queue, sojourn,
congestion-window, FlowMonitor, and log files, plus separate PNG plots.

* **E1** uses the available standard `TcpDctcp` behavior for every flow. Its utility weight is 1, so the mapping reduces to the unmodified DCTCP ECN response.
* **E2** applies the paper-style fixed weights `(0.9, 0.6, 0.5, 0.2)` for the whole run.
* **E3** applies the project activity schedule at 0, 30, 60, and 80 seconds.

The C++ program writes FlowMonitor XML, per-application metrics, network mark/drop and weighted-satisfaction metrics, cwnd transitions, aggregate queue occupancy samples, and Classic/L4S sojourn samples. The analyzer combines the three runs, including p95/p99 delay bins from FlowMonitor and p95/p99 queue/sojourn samples.

This ns-3 checkout has no TCP Prague or Accurate ECN implementation. E1 is therefore the equal-weight `TcpDctcp` baseline, and the utility mapping is applied to DCTCP's measured ECN fraction. Results should be described as a DCTCP-based proxy experiment rather than a reproduction of the paper's Prague results. Each app's satisfaction is `min(throughput / offered load, 1)`. The network weighted-utility score applies the same time-averaged dynamic activity profile to E1, E2, and E3, then normalizes by the sum of mean target utilities; `mean_control_utility` and `mean_target_utility` are both retained per application.
