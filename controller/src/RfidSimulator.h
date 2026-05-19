#pragma once
#include <optional>
#include <random>
#include <string>
#include <vector>

struct RfidTag {
    std::string epc;        // 16-char hex EPC code
    std::string location;   // station identifier
    int64_t     ts_us;      // microseconds since epoch
};

// Simulates an RFID reader polling a pool of known tags.
// Stateless between scans — each call is an independent Bernoulli trial.
class RfidSimulator {
public:
    explicit RfidSimulator(uint32_t seed = 42, size_t pool_size = 8);

    // Returns a tag with probability p_detect (default 0.3 per scan).
    std::optional<RfidTag> scan();

    // Force the next scan() to return a specific tag regardless of probability.
    void inject(const std::string& epc);

    const std::vector<std::string>& pool() const { return pool_; }

private:
    std::mt19937                           rng_;
    std::vector<std::string>               pool_;
    std::bernoulli_distribution            trigger_{0.3};
    std::uniform_int_distribution<size_t>  pick_;
    std::optional<std::string>             pending_;

    static std::string generate_epc(std::mt19937& rng);
};
