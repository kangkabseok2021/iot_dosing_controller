#include "FlowSensor.h"
#include <cmath>

FlowSensor::FlowSensor(double k_factor, uint32_t seed)
    : k_factor_(k_factor), rng_(seed) {}

FlowReading FlowSensor::read(double target_flow_ml_min) {
    // target frequency from target flow: f = Q / k
    double target_freq = target_flow_ml_min / k_factor_;
    double noisy_freq  = target_freq * (1.0 + noise_pct_(rng_));
    if (noisy_freq < 0.0) noisy_freq = 0.0;
    double flow = k_factor_ * noisy_freq;
    return {flow, noisy_freq, flow > LOW_THRESHOLD_ML_MIN};
}
