#pragma once

#include <chrono>

#include <nlohmann/json.hpp>

namespace openvprof {

class Record {
    public:
        virtual nlohmann::json to_json() const = 0;
        virtual ~Record() {}

};

class InstantRecord : public Record {
    public:
        InstantRecord(std::chrono::high_resolution_clock::time_point &when) : when_(when) {}

    protected:
        std::chrono::high_resolution_clock::time_point when_;

    public:
        virtual nlohmann::json to_json() const {
            return nlohmann::json{{"wall_time_point_ns", std::chrono::duration_cast<std::chrono::nanoseconds>(when_.time_since_epoch()).count()}};
        }

};

class SpanRecord : public Record {
    public:
    SpanRecord(
        std::chrono::high_resolution_clock::time_point start, 
        std::chrono::duration<double> duration
    ) : start_(start), duration_(duration) {}

    protected:
    std::chrono::high_resolution_clock::time_point start_;
    std::chrono::duration<double> duration_;

    public:
        virtual nlohmann::json to_json() const {
            return nlohmann::json{
                {"wall_start_ns", std::chrono::duration_cast<std::chrono::nanoseconds>(start_.time_since_epoch()).count()},
                {"wall_duration_ns", std::chrono::duration_cast<std::chrono::nanoseconds>(duration_).count()}
            };
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

class CuptiActivityKernelRecord : public SpanRecord {
public:
    nlohmann::json to_json() const override;
};

// convert any record to json implicitly
static void to_json(nlohmann::json &j, const Record &r) {
    j = r.to_json();
}

}