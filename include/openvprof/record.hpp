#pragma once

#include <chrono>

#include <nlohmann/json.hpp>

namespace openvprof{

class Record {
    public:
        virtual nlohmann::json to_json() const = 0;

};

class SampleRecord {
    public:
        SampleRecord(std::chrono::high_resolution_clock::time_point &when) : when_(when) {}

    protected:
        std::chrono::high_resolution_clock::time_point when_;

    public:
        virtual nlohmann::json to_json() const = 0;
        nlohmann::json timestamp_json() const {
            return nlohmann::json{{"wall_time_point_ns", std::chrono::duration_cast<std::chrono::nanoseconds>(when_.time_since_epoch()).count()}};
        }

};

class NvmlCudaDriverVersionRecord : public Record {
 public:
  int version;
  nlohmann::json to_json() const override;
};

class NvmlPstateRecord : public Record {
 public:
  int pstate_;
  nlohmann::json to_json() const override;
};

// convert any record to json implicitly
static void to_json(nlohmann::json &j, const Record &r) {
    j = r.to_json();
}

}