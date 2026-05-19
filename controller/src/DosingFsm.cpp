#include "DosingFsm.h"

const char* dosing_state_name(DosingState s) noexcept {
    switch (s) {
        case DosingState::IDLE:     return "IDLE";
        case DosingState::DOSING:   return "DOSING";
        case DosingState::PAUSE:    return "PAUSE";
        case DosingState::COMPLETE: return "COMPLETE";
    }
    return "UNKNOWN";
}

DosingFsm::DosingFsm(double target_volume_ml)
    : target_volume_ml_(target_volume_ml) {}

void DosingFsm::reset() noexcept {
    state_          = DosingState::IDLE;
    accumulated_ml_ = 0.0;
    active_tag_.clear();
}

void DosingFsm::update(bool valve_cmd, bool reset_cmd,
                        const FlowReading& flow,
                        const std::optional<RfidTag>& rfid,
                        double dt_s) {
    if (reset_cmd) { reset(); return; }

    switch (state_) {
        case DosingState::IDLE:
            if (rfid && valve_cmd) {
                active_tag_ = rfid->epc;
                state_      = DosingState::DOSING;
            }
            break;

        case DosingState::DOSING:
            accumulated_ml_ += flow.flow_rate_ml_min * (dt_s / 60.0);
            if (accumulated_ml_ >= target_volume_ml_) {
                state_ = DosingState::COMPLETE;
            } else if (!valve_cmd) {
                state_ = DosingState::PAUSE;
            }
            break;

        case DosingState::PAUSE:
            if (valve_cmd) state_ = DosingState::DOSING;
            break;

        case DosingState::COMPLETE:
            break;   // latches until reset
    }
}
