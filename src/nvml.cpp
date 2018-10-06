
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

void Poller::start()
{
    LOG(debug, "nvml scanning system");

    // CUDA driver
    {
        auto *r = new NvmlCudaDriverVersionRecord;
        nvmlSystemGetCudaDriverVersion(&r->version);
        records_->push(r);
    }
    // Device handles
    unsigned int num_devices;
    NVML_CHECK(nvmlDeviceGetCount(&num_devices));
    LOG(debug, "nvml got {} devices", num_devices);
    devices_.resize(num_devices);
    
    for (unsigned int i = 0; i < devices_.size(); ++i)
    {
        NVML_CHECK(nvmlDeviceGetHandleByIndex(i, &devices_[i]));
    }

    // cache nvlinks
    active_nvlink_ids_.resize(devices_.size());
    for (unsigned int devIdx = 0; devIdx < devices_.size(); ++devIdx)
    {
        auto dev = devices_[devIdx];
        for (size_t i = 0; i < NVML_NVLINK_MAX_LINKS; ++i)
        {
            nvmlEnableState_t isActive;
            nvmlReturn_t result = nvmlDeviceGetNvLinkState(dev, i, &isActive);
            if (NVML_ERROR_INVALID_ARGUMENT == result)
            { // device or link is invalid
                continue;
            }
            NVML_CHECK(result);
            if (isActive == NVML_FEATURE_ENABLED)
            {
                LOG(debug, "NVLink {} for device {} is active", i, devIdx);
                active_nvlink_ids_[devIdx].push_back(i);
            }
        }
    }

    // Reset NVLink utilization counters
    for (unsigned int devIdx = 0; devIdx < devices_.size(); ++devIdx)
    {
        auto dev = devices_[devIdx];
        for (auto linkIdx : active_nvlink_ids_[devIdx]) {
            nvmlNvLinkUtilizationControl_t ctl;
            NVML_CHECK(nvmlDeviceGetNvLinkUtilizationControl(dev, linkIdx, 0, &ctl));
            ctl.units=NVML_NVLINK_COUNTER_UNIT_BYTES;
            ctl.pktfilter=NVML_NVLINK_COUNTER_PKTFILTER_ALL;
            NVML_CHECK(nvmlDeviceSetNvLinkUtilizationControl(dev, linkIdx, 0, &ctl, 1));
            NVML_CHECK(nvmlDeviceGetNvLinkUtilizationControl(dev, linkIdx, 1, &ctl));
            ctl.units=NVML_NVLINK_COUNTER_UNIT_BYTES;
            ctl.pktfilter=NVML_NVLINK_COUNTER_PKTFILTER_ALL;
            NVML_CHECK(nvmlDeviceSetNvLinkUtilizationControl(dev, linkIdx, 1, &ctl, 1));
            NVML_CHECK(nvmlDeviceFreezeNvLinkUtilizationCounter (dev, linkIdx, 0, NVML_FEATURE_DISABLED)); 
            NVML_CHECK(nvmlDeviceFreezeNvLinkUtilizationCounter (dev, linkIdx, 1, NVML_FEATURE_DISABLED)); 
        }
    }
    

    // start the polling thread
    LOG(debug, "running nvml polling thread");
    signal_ = Signal::CONTINUE;
    thread_ = std::thread(&Poller::run, this);
}

void Poller::run()
{

    // Watch the NVML values of interest
    while (signal_ == Signal::CONTINUE)
    {
        LOG(trace, "nvml polling thread wakeup");


        // get PSTATE of all devices
        LOG(trace, "nvml polling getting pstates");
        for (size_t device_idx = 0; device_idx < devices_.size(); ++device_idx)
        {
            auto dev = devices_[device_idx];
            nvmlPstates_t pState;
            NVML_CHECK(nvmlDeviceGetPerformanceState(dev, &pState));
            auto timestamp = std::chrono::high_resolution_clock::now();

            {
                auto *r = new NvmlPstateRecord(device_idx, timestamp, pState);
                records_->push(r);
            }
        }

        // Get NVLink traffic on all devices
        LOG(trace, "nvml polling nvlink counters");
        for (size_t devIdx = 0; devIdx < devices_.size(); ++devIdx)
        {
            auto dev = devices_[devIdx];
            for (auto linkIdx : active_nvlink_ids_[devIdx]) {
                unsigned long long tx;
                unsigned long long rx;
                NVML_CHECK(nvmlDeviceGetNvLinkUtilizationCounter(dev, linkIdx, 0, &rx, &tx ));
                LOG(trace, "dev:{} link:{} ctr:0 rx:{} tx:{}", devIdx, linkIdx, rx, tx);
                NVML_CHECK(nvmlDeviceGetNvLinkUtilizationCounter(dev, linkIdx, 1, &rx, &tx ));
                LOG(trace, "dev:{} link:{} ctr:1 rx:{} tx:{}", devIdx, linkIdx, rx, tx);
            }


            
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
}

} // namespace nvml
} // namespace openvprof
