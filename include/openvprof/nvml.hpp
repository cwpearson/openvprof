#pragma once

#include <chrono>
#include <thread>

#include <boost/lockfree/queue.hpp>
#include <nvml.h>

#include "openvprof/record.hpp"

namespace openvprof
{
namespace nvml
{

void init();
void fini();

class Poller
{
  public:
    enum class Signal
    {
        CONTINUE,
        STOP
    };

    Poller(boost::lockfree::queue<Record *> *records)
        : records_(records), signal_(Signal::STOP)
    {
    }

    // create and start the polling thread
    void start();

    // finish the polling thread
    void stop()
    {
        signal_ = Signal::STOP;
        LOG(trace, "waiting for join");
        thread_.join();
    }

    void pause()
    {
        LOG(warn, "ignoring pause");
    }

    void resume()
    {
        LOG(warn, "ignoring resume");
    }

  private:
    boost::lockfree::queue<Record *> *records_;
    volatile Signal signal_;
    std::thread thread_;
    std::vector<nvmlDevice_t> devices_; // nvmlDevice handles by index
    std::vector<std::vector<unsigned int>> active_nvlink_ids_; // ids of active nvlinks by device index

    // the code executed by the polling thread
    void run();
};

} // namespace nvml
} // namespace openvprof
