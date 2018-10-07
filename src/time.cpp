#include "openvprof/time.hpp"

#include <chrono>

namespace openvprof {

    time_point now() {
        return std::chrono::high_resolution_clock::now();
    }

    size_t ns_since_epoch(const time_point &t) {
        return std::chrono::duration_cast<std::chrono::nanoseconds>(t.time_since_epoch()).count();
    }

}