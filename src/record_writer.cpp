#include "openvprof/record_writer.hpp"

#include <chrono>
#include <fstream>

using namespace openvprof;

void RecordWriter::run() {
    bool first_record = true;

    std::ofstream file(output_path_);

    file << "[\n";

    Record *r;

    while(Signal::CONTINUE == signal_) {
        while(records_->pop(r)) {
            nlohmann::json j = *r;
            delete r;
            r = nullptr;

            if (!first_record) {
                file << ",\n";
            }

            LOG(trace, "write {}", j.dump());
            file << j;
            first_record = false;
        }
        LOG(trace, "sleeping record writer");
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        LOG(trace, "wakeup record writer");
    }

    LOG(debug, "RecordWriter::run(): final flush");
    while(records_->pop(r)) {
            nlohmann::json j = *r;
            delete r;
            r = nullptr;

            if (!first_record) {
                file << ",\n";
            }

            LOG(trace, "write {}", j.dump());
            file << j;
            first_record = false;
    }

    file << "\n]\n";

}