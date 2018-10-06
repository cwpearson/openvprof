#pragma once

#include <chrono>

namespace openvprof {

    typedef std::chrono::high_resolution_clock::time_point time_point;

    static time_point now() {
        return std::chrono::high_resolution_clock::now();
    }

    static size_t ns_since_epoch(const time_point &t) {
        return std::chrono::duration_cast<std::chrono::nanoseconds>(t.time_since_epoch()).count();
    }

}