#include <cupti.h>
#include <iostream>

#include "openvprof/logger.hpp"

class Profiler {
  public:
    Profiler(); 

   CUpti_SubscriberHandle subscriber;

 
};

Profiler::Profiler() {
  std::cerr << "hello from std::cerr\n";

  if (!logger::console || logger::console->name() != "openvprof") {
    logger::console  = spdlog::stderr_logger_mt("openvprof");
  }
  logger::console->info("Hello from the logger");
}

static Profiler p;
