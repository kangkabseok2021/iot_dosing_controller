#include "RfidSimulator.h"
#include <chrono>
#include <iomanip>
#include <sstream>

static std::string to_hex(uint8_t byte) {
    std::ostringstream ss;
    ss << std::hex << std::setfill('0') << std::setw(2) << std::uppercase
       << static_cast<int>(byte);
    return ss.str();
}

std::string RfidSimulator::generate_epc(std::mt19937& rng) {
    std::uniform_int_distribution<uint8_t> byte_dist(0, 255);
    std::string epc;
    epc.reserve(16);
    for (int i = 0; i < 8; ++i) epc += to_hex(byte_dist(rng));
    return epc;
}

RfidSimulator::RfidSimulator(uint32_t seed, size_t pool_size)
    : rng_(seed), pick_(0, pool_size - 1)
{
    pool_.reserve(pool_size);
    for (size_t i = 0; i < pool_size; ++i)
        pool_.push_back(generate_epc(rng_));
}

std::optional<RfidTag> RfidSimulator::scan() {
    std::string epc;
    if (pending_) {
        epc = *pending_;
        pending_.reset();
    } else if (!trigger_(rng_)) {
        return std::nullopt;
    } else {
        epc = pool_[pick_(rng_)];
    }

    auto ts = std::chrono::system_clock::now().time_since_epoch();
    return RfidTag{epc, "station-1",
                   std::chrono::duration_cast<std::chrono::microseconds>(ts).count()};
}

void RfidSimulator::inject(const std::string& epc) { pending_ = epc; }
