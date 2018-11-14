# openvprof Project

A collection of profiling tools, inspired by challenges in profiling large CUDA applications using `nvprof` and `nvvp`.

## scripts/openvprof.py

A trace analysis tool that can report _exposed_ GPU activities - GPU activites that actually contribute to the overall program execution time.

### example

```
$ ./openvprof.py --helpUsage: openvprof.py [OPTIONS] COMMAND [ARGS]...

Options:
  --debug  print debugging messages
  --help   Show this message and exit.

Commands:
  driver-time   Show a histogram of driver API times
  filter        filter file INPUT to contain only records between START and...
  kernel-time   Show a histogram of kernel times (ns)
  list-edges
  list-ranges   print summary statistics of ranges
  list-records
  stats
  summary
  timeline      Generate a chrome:://tracing timeline
```

```
$ ./openvprof.py summary -r CUDATreeLearner::Train  ~/ibmGBT_data/timeline.nvprof
Selected timeslices cover 19.952495698s
Marker Report
=============
<not implemented>

Communication Report
====================
Active communication Time-Slices: 6.124770744s
Exposed communication Time-Slices: 2.315078656s
Active Communication Time-Slices
--------------------------------
  cpu-gpu0 6.122501773s
  gpu0-cpu 0.002268971s
  gpu0-gpu0 0.0s
  gpu0-gpu1 0.0s
  gpu0-gpu2 0.0s
  gpu0-gpu3 0.0s
  cpu-gpu1 0.0s
  gpu1-cpu 0.0s
  gpu1-gpu0 0.0s
  gpu1-gpu1 0.0s
  gpu1-gpu2 0.0s
  gpu1-gpu3 0.0s
  cpu-gpu2 0.0s
  gpu2-cpu 0.0s
  gpu2-gpu0 0.0s
  gpu2-gpu1 0.0s
  gpu2-gpu2 0.0s
  gpu2-gpu3 0.0s
  cpu-gpu3 0.0s
  gpu3-cpu 0.0s
  gpu3-gpu0 0.0s
  gpu3-gpu1 0.0s
  gpu3-gpu2 0.0s
  gpu3-gpu3 0.0s
Exposed communication breakdown
-------------------------------
Runtime Report
==============
Any CUDA Runtime Time-Slices: 5.527960601s
Exposed CUDA Runtime Time-Slices: 0.307504125s
Exposed Runtime by Thread
-------------------------
  1917872512 0.307504125s
Any Runtime by Call
-----------------------
  cudaMemcpyAsync 3.366746327s
  cudaEventSynchronize 2.095184403s
  cudaLaunchKernel 0.031538696s
  cudaEventRecord 0.025995506s
  cudaDeviceSynchronize 0.005472751s
  cudaStreamSynchronize 0.00254224s
  cudaGetLastError 0.000480678s
Exposed Runtime by Call
-----------------------
  cudaMemcpyAsync 0.254882977s
  cudaLaunchKernel 0.029222504s
  cudaEventSynchronize 0.011957917s
  cudaDeviceSynchronize 0.005472751s
  cudaEventRecord 0.003424999s
  cudaStreamSynchronize 0.00254224s
  cudaGetLastError 7.37e-07s
Exposed Runtime Breakdown
-------------------------
  (53816, 1917872512, 'cudaMemcpyAsync') 0.254882977s
  (53816, 1917872512, 'cudaLaunchKernel') 0.029222504s
  (53816, 1917872512, 'cudaEventSynchronize') 0.011957917s
  (53816, 1917872512, 'cudaDeviceSynchronize') 0.005472751s
  (53816, 1917872512, 'cudaEventRecord') 0.003424999s
  (53816, 1917872512, 'cudaStreamSynchronize') 0.00254224s
  (53816, 1917872512, 'cudaGetLastError') 7.37e-07s
Any Runtime Breakdown
---------------------
  (53816, 1917872512, 'cudaMemcpyAsync') 3.366746327s
  (53816, 1917872512, 'cudaEventSynchronize') 2.095184403s
  (53816, 1917872512, 'cudaLaunchKernel') 0.031538696s
  (53816, 1917872512, 'cudaEventRecord') 0.025995506s
  (53816, 1917872512, 'cudaDeviceSynchronize') 0.005472751s
  (53816, 1917872512, 'cudaStreamSynchronize') 0.00254224s
  (53816, 1917872512, 'cudaGetLastError') 0.000480678s
Kernel Report
=============
Any GPU Kernel Time-Slices: 1.411868259s
Exposed GPU Kernel Time-Slices: 0.001103871s
Active kernel time-slices by GPU
--------------------------------
  GPU 0 Kernel Time: 1.411868259s
  GPU 1 Kernel Time: 0.0s
  GPU 2 Kernel Time: 0.0s
  GPU 3 Kernel Time: 0.0s
Active kernel time-slices on GPU 0
-----------------------------------
  _Z12histogram256PK6uchar4S1_jPKjjPKfS5_PcPViPfm 0.813565823s
  _Z21histogram256_fulldataPK6uchar4S1_jPKjjPKfS5_PcPViPfm 0.598302436s
```

## openvprof

An open CUDA GPU profiler using CuPTI and Nvidia Management Library.

### Build/Run a docker image

docker build -f ppc64le.Dockerfile -t openvprof/ppc64le .
docker run -v `pwd`/container:/host -it openvprof/ppc64le

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

## Acknowledgements

These tools were conceived and partially prototyped at IBM's T.J. Watson Research Center during a fall 2018 internship
