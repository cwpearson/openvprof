#include <cupti.h>
#include <cstdio>
#include <iostream>
#include <thread>
#include <chrono>

#include "openvprof/logger.hpp"
#include "openvprof/record.hpp"
#include "openvprof/cupti_activity.hpp"

#include <boost/lockfree/queue.hpp>
#include <boost/process/system.hpp>
using namespace boost::lockfree;


class Profiler {
  public:
    Profiler(); 
    ~Profiler();
  private:
   queue<Record*> records_;  
   CUpti_SubscriberHandle subscriber;
   std::thread nvml_poller_;
   std::thread record_writer_;
 
};

volatile int nvml_poll_stop = false;

void nvml_poll() {
  while (!nvml_poll_stop) {
    logger::console->info("nvml poller...");
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
  }
}

void record_writer(queue<Record*> &records) {
  Record *record;
  while (records.pop(record)) {
    logger::console->info("dumped record");
  }
}


Profiler::Profiler() : records_(128)  {
  std::cerr << "hello from std::cerr\n";

  if (!logger::console || logger::console->name() != "openvprof") {
    logger::console  = spdlog::stderr_logger_mt("openvprof");
  }
  LOG(info, "Hello from the logger");

  openvprof::initTrace();

  nvml_poller_ = std::thread(nvml_poll);
  record_writer_ = std::thread(record_writer, std::ref(records_));
}

Profiler::~Profiler() {
  logger::console->info("finalizing profiler.");

  LOG(info, "finalizing CUPTI activity API");
  openvprof::finalizeTrace();

  logger::console->info("stopping nvml poller...");
  nvml_poll_stop = true;
  logger::console->info("waiting for nvml poller...");
  nvml_poller_.join();
  logger::console->info("waiting for record writer...");
  record_writer_.join();
  logger::console->flush();
}

static Profiler global;

int main(int argc, char **argv) {

  namespace bp = boost::process; //we will assume this for all further examples

  if (argc > 1) {
    std::string cmd;
    for (int i = 1; i < argc; ++i) {
      cmd += std::string(argv[i]) + " ";
    }
    logger::console->info("Running {}", cmd);
    auto c = bp::child(cmd);
    c.wait();
    int ret = c.exit_code();

  }

  return 0;
}

