#include <cstdlib>
#include <cstdio>
#include <iostream>
#include <thread>
#include <chrono>

#include <cupti.h>

#include "openvprof/logger.hpp"
#include "openvprof/record.hpp"
#include "openvprof/record_writer.hpp"
#include "openvprof/cupti_activity.hpp"
#include "openvprof/nvml.hpp"

#include <boost/lockfree/queue.hpp>
#include <boost/process/system.hpp>

using namespace boost::lockfree;
using openvprof::Record;
using openvprof::RecordWriter;


class Profiler {
  public:
    Profiler(); 
    ~Profiler();
  private:
   queue<Record*> records_;  
   CUpti_SubscriberHandle subscriber;
   openvprof::nvml::Poller nvml_poller_;
   openvprof::RecordWriter record_writer_;

};



Profiler::Profiler() : records_(128), nvml_poller_(&records_)  {
  if (!logger::console || logger::console->name() != "openvprof") {
    logger::console  = spdlog::stderr_logger_mt("openvprof");
  }

  std::string log_level("warn");
  {
    char *c = std::getenv("OPENVPROF_LOG_LEVEL");
    if (c) {
      log_level = c;
    }
  }
  if ("trace" == log_level) {
    logger::console->set_level(spdlog::level::trace);
  } else if ("debug" == log_level) {
    logger::console->set_level(spdlog::level::debug);
  } else if ("info" == log_level) {
    logger::console->set_level(spdlog::level::info);
  } else if ("warn" == log_level) {
    logger::console->set_level(spdlog::level::warn);
  } else if ("err" == log_level) {
    logger::console->set_level(spdlog::level::err);
  } else if ("crit" == log_level) {
    logger::console->set_level(spdlog::level::critical);
  } else {
    LOG(warn, "Unrecognized log level: {}. Try [trace, debug, info, warn (default), err, crit]", log_level);
  }



  LOG(debug, "Hello from the logger");


  std::string output_path("openvprof.json");
  {
    char *c = std::getenv("OPENVPROF_OUTPUT_PATH");
    if (c) {
      output_path = c;
    }
  }
  LOG(debug, "Output path is {}", output_path);

  record_writer_ = RecordWriter(&records_, output_path);
  record_writer_.start();

  // init CUPTI activity API
  openvprof::initTrace(&records_);

  // init nvml
  openvprof::nvml::init();

  // start the polling thread
  nvml_poller_.start();
  
}

Profiler::~Profiler() {
  LOG(trace, "finalizing profiler.");

  LOG(info, "finalizing CUPTI activity API");
  openvprof::finalizeTrace();

  LOG(trace, "stopping nvml poller...");
  nvml_poller_.stop();
  LOG(trace, "stoped nvml poller");


  LOG(trace, "waiting for record writer...");
  record_writer_.stop();
  LOG(trace, "record writer finished.");
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
    (void)ret;

  }

  return 0;
}

