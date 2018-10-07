
#include <nvml.h>
#include <iostream>
#include <vector>
#include <array>

#include "openvprof/logger.hpp"
#include "openvprof/nvml.hpp"
#include "openvprof/nvml_record.hpp"
#include "openvprof/nvml_utils.hpp"

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

namespace openvprof {
    namespace nvml {



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
            else if (NVML_ERROR_NOT_SUPPORTED) {
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

    std::vector<std::array<std::array<unsigned long long, 2>, NVML_NVLINK_MAX_LINKS>> rxs;
    std::vector<std::array<std::array<unsigned long long, 2>, NVML_NVLINK_MAX_LINKS>> txs;
    rxs.resize(devices_.size());
    txs.resize(devices_.size());
    for (auto &a : rxs) {
        a = {0};
    }
    for (auto &v : txs) {
        v = {0};
    }


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
                auto time = now();
                NVML_CHECK(nvmlDeviceGetNvLinkUtilizationCounter(dev, linkIdx, 0, &rx, &tx));
                LOG(trace, "dev:{} link:{} ctr:0 rx:{} tx:{}", devIdx, linkIdx, rx, tx);
                if (tx < txs[devIdx][linkIdx][0]) {
                    LOG(warn, "tx counter rollover");
                }
                if (rx < rxs[devIdx][linkIdx][0]) {
                    LOG(warn, "rx counter rollover");
                }
                txs[devIdx][linkIdx][0] = tx;
                rxs[devIdx][linkIdx][0] = rx;
                {
                    auto *r = new NvmlNvlinkUtilizationCounterRecord(
                        time,
                        devIdx,
                        linkIdx,
                        tx,
                        0,
                        true
                    );
                    records_->push(r);
                }
                {
                    auto *r = new NvmlNvlinkUtilizationCounterRecord(
                        time,
                        devIdx,
                        linkIdx,
                        rx,
                        0,
                        false
                    );
                    records_->push(r);
                }


                time = now();
                NVML_CHECK(nvmlDeviceGetNvLinkUtilizationCounter(dev, linkIdx, 1, &rx, &tx ));
                LOG(trace, "dev:{} link:{} ctr:1 rx:{} tx:{}", devIdx, linkIdx, rx, tx);
                if (tx < txs[devIdx][linkIdx][1]) {
                    LOG(warn, "tx counter rollover");
                }
                if (rx < rxs[devIdx][linkIdx][1]) {
                    LOG(warn, "rx counter rollover");
                }
                txs[devIdx][linkIdx][1] = tx;
                rxs[devIdx][linkIdx][1] = rx;

                {
                    auto *r = new NvmlNvlinkUtilizationCounterRecord(
                        time,
                        devIdx,
                        linkIdx,
                        tx,
                        1,
                        true
                    );
                    records_->push(r);
                }
                {
                    auto *r = new NvmlNvlinkUtilizationCounterRecord(
                        time,
                        devIdx,
                        linkIdx,
                        rx,
                        1,
                        false
                    );
                    records_->push(r);
                }

            }
            
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
}


    } // namepsace nvmp
} // namespace openvprof