#pragma once
#include <random>

struct FlowReading {
    double flow_rate_ml_min;  // Q = k × f (calibrated)
    double pulse_freq_hz;     // raw frequency
    bool   is_flowing;        // Q > low_threshold
};

// Models a pulse-frequency flow sensor: Q = k_factor × f.
// Gaussian noise (σ = 2% of target) added to pulse frequency.
class FlowSensor {
public:
    explicit FlowSensor(double k_factor = 5.0, uint32_t seed = 42);

    // Simulate a reading for the given target flow (ml/min).
    FlowReading read(double target_flow_ml_min);

    static constexpr double LOW_THRESHOLD_ML_MIN  = 10.0;  // below = occlusion
    static constexpr double HIGH_THRESHOLD_ML_MIN = 500.0; // above = overflow

private:
    double k_factor_;
    std::mt19937 rng_;
    std::normal_distribution<double> noise_pct_{0.0, 0.02};  // 2% σ
};
