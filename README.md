# openvprof Project

A collection of profiling tools, inspired by challenges in profiling large CUDA applications using `nvprof` and `nvvp`.

## scripts/pynvtx.py

A python wrapper for adding Nvidia Tools Extension ranges for python functions to `nvprof` profiles.

### Run Natively

`nvprof pynvtx.py <your python script and args>`

### Add to a Docker image

```docker
RUN apt-get update && apt-get install python3
```

#### Options

`--depth DEPTH`: only record ranges to this stack dept
`--verbose` / `--debug` print verbose information / print debug messages

## openvprof

An open profiler using CuPTI and Nvidia Management Library

### Building

```bash
mkdir build
cd build
cmake ..
make
```

### Recording

Run a CUDA program and produce an output record `openvprof.json`

```bash
LD_PRELOAD=libopenvprof.so ./my-exe
```

#### Options

* `OPENVPROF_LOG_LEVEL`: `trace`, `debug`, `info`, `warn`, `err`, `crit`
* `OPENVPROF_OUTPUT_PATH`: control the output path that can be loaded into chrome://tracing

### Visualizing

Convert `openvprof.json` to `trace.json`

```bash
python3 scrips/trace.py
```

Open Chromium or Chrome to `chrome://tracing` and load `trace.json`


### Features

Recording:

- [x] Kernel activity
- [x] Memcpy activity
- [x] raw NVLink traffic
- [ ] raw PCIe traffic
- [ ] Defer writing report to disk with `OPENVPROF_DEFER_IO` env variable

Visualizing:
- [ ] logical link traffic visualization
- [ ] physical link traffic visualization
- [ ] Split or combine different transfer directions on same link

## scripts / nvprof_to_trace.py

Analsys of files generated from nvprof

- [ ] Basic Kernel Stats
  - [ ] Histogram run times
    - [x] Overall histogram
    - [ ] per-device histogram
  - [ ] Occupancy over entire execution profile
  - [ ] Occupancy over kernel executions
- [ ] Basic transfer times stats
  - [x] Overall transfer times stats
- [ ] Activity Overlap
  - [x] Divide into fixed-size bins, per-bin expected overlap
