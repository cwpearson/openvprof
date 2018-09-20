
#include <nvml.h>

#include "openvprof/logger.hpp"
#include "openvprof/nvml.hpp"

namespace openvprof {
namespace nvml {

void init() {
    nvmlInit();
}

void fini() {
    nvmlShutdown();
}


void Poller::run() {

      // Query some system info and insert records

      auto *r = new NvmlCudaDriverVersionRecord;
      nvmlSystemGetCudaDriverVersion(&r->version);
      records_->push(r);

      // Watch the NVML values of interest
      while(signal_ == Signal::CONTINUE) {
          LOG(trace, "polling nvml");
          std::this_thread::sleep_for(std::chrono::milliseconds(500));
      }
}

} // namespace nvml
} // namespace openvprof

