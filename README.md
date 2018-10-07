# openvprof

An open version of `nvprof` and `nvvp`.

## Building

```bash
mkdir build
cd build
cmake ..
make
```

## Running

Run a CUDA program and produce an output record `openvprof.json`

```bash
LD_PRELOAD=libopenvprof.so ./my-exe
```

Unlike the files produced by nvprof, you can read and parse this one easily.


## Visualizing

Convert `openvprof.json` to `trace.json`

```bash
python3 scrips/trace.py
```

Open Chromium or Chrome to `chrome://tracing` and load `trace.json`

## Environment variables:

* `OPENVPROF_LOG_LEVEL`: `trace`, `debug`, `info`, `warn`, `err`, `crit`
* `OPENVPROF_OUTPUT_PATH`: control the output path that can be loaded into chrome://tracing

## Coming soon:

Recording:

- [ ] NVLink traffic reporting
- [ ] PCIe traffic reporting

Tracing:

- [ ] per-link traffic visualization