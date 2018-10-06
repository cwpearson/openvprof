
#include <nvml.h>
#include <iostream>

#include "openvprof/logger.hpp"
#include "openvprof/nvml.hpp"
#include "openvprof/nvml_record.hpp"

#define NVML_CHECK(ans)                        \
    {                                          \
        nvmlAssert((ans), __FILE__, __LINE__); \
    }
inline void nvmlAssert(nvmlReturn_t code, const char *file, int line,
                       bool abort = true)
{
    if (code != NVML_SUCCESS)
    {
        const char *errstr = nvmlErrorString(code);
        // std::cerr << "NVML_CHECK: " << errstr << " " << file << " " << line << std::endl;
        LOG(error, "NVML_CHECK: {}, {} {}", errstr, file, line);
        if (abort)
            exit(code);
    }
}

namespace openvprof
{
namespace nvml
{

void init()
{
    nvmlInit();
}

void fini()
{
    nvmlShutdown();
}

void Poller::run()
{
    // Query some system info and insert records

    // CUDA driver version
    {
        auto *r = new NvmlCudaDriverVersionRecord;
        nvmlSystemGetCudaDriverVersion(&r->version);
        records_->push(r);
    }

    // Device handles
    unsigned int num_devices;
    NVML_CHECK(nvmlDeviceGetCount(&num_devices));
    LOG(debug, "nvml got {} devices", num_devices);
    std::vector<nvmlDevice_t> devices(num_devices);

    for (unsigned int i = 0; i < devices.size(); ++i)
    {
        NVML_CHECK(nvmlDeviceGetHandleByIndex(i, &devices[i]));
    }

    // Watch the NVML values of interest
    while (signal_ == Signal::CONTINUE)
    {
        LOG(trace, "polling nvml");

        for (size_t device_idx = 0; device_idx < devices.size(); ++device_idx)
        {
            auto dev = devices[device_idx];
            nvmlPstates_t pState;
            NVML_CHECK(nvmlDeviceGetPerformanceState(dev, &pState));
            auto timestamp = std::chrono::high_resolution_clock::now();

            {
                auto *r = new NvmlPstateRecord(device_idx, timestamp, pState);
                records_->push(r);
            }
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
}

} // namespace nvml
} // namespace openvprof

// nvmlReturn_t nvmlDeviceGetNvLinkUtilizationCounter ( nvmlDevice_t device, unsigned int  link, unsigned int  counter, unsigned long long* rxcounter, unsigned long long* txcounter )