#pragma once

#include <chrono>
#include <thread>

#include <boost/lockfree/queue.hpp>

#include "openvprof/record.hpp"

namespace openvprof {
namespace nvml {


void init();
void fini();

class Poller {
public:
    enum class Signal {
        CONTINUE,
        STOP
    };

  Poller(boost::lockfree::queue<Record*> *records) 
  : records_(records), signal_(Signal::STOP) {


  }

  // create and start the polling thread
  void start() {
      signal_ = Signal::CONTINUE;
      LOG(trace, "starting thread");
      thread_ = std::thread(&Poller::run, this);
  }

  // finish the polling thread
  void stop() {
      signal_ = Signal::STOP;
      LOG(trace, "waiting for join");
      thread_.join();
  }

  void pause() {
      LOG(warn, "ignoring pause");
  }

  void resume() {
      LOG(warn, "ignoring resume");
  }



private:
  boost::lockfree::queue<Record*> *records_;
  volatile Signal signal_;
  std::thread thread_;


  // the code executed by the polling thread
  void run();


};



} // namespace nvml
} // namespace openvprof
