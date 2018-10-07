# openvprof

An open version of `nvprof` and `nvvp`.

## Building

```bash
mkdir build
cd build
cmake ..
make
```

## Recording

Run a CUDA program and produce an output record `openvprof.json`

```bash
LD_PRELOAD=libopenvprof.so ./my-exe
```

Unlike the files produced by nvprof, you can read and parse this one easily.

### Options

* `OPENVPROF_LOG_LEVEL`: `trace`, `debug`, `info`, `warn`, `err`, `crit`
* `OPENVPROF_OUTPUT_PATH`: control the output path that can be loaded into chrome://tracing

## Visualizing

Convert `openvprof.json` to `trace.json`

```bash
python3 scrips/trace.py
```

Open Chromium or Chrome to `chrome://tracing` and load `trace.json`


## Features

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