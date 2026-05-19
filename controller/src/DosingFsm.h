#pragma once
#include "FlowSensor.h"
#include "RfidSimulator.h"
#include <chrono>
#include <optional>
#include <string>

enum class DosingState { IDLE, DOSING, PAUSE, COMPLETE };

const char* dosing_state_name(DosingState s) noexcept;

// Four-state dosing FSM.
//   IDLE     → DOSING   when RFID tag detected AND valve_cmd = 1
//   DOSING   → PAUSE    when valve_cmd = 0
//   DOSING   → COMPLETE when accumulated_ml >= target_volume_ml
//   PAUSE    → DOSING   when valve_cmd = 1
//   any      → IDLE     when reset_cmd = 1
class DosingFsm {
public:
    explicit DosingFsm(double target_volume_ml = 1000.0);

    // Drive one cycle.  dt_s = elapsed seconds since last call.
    void update(bool valve_cmd, bool reset_cmd,
                const FlowReading& flow,
                const std::optional<RfidTag>& rfid,
                double dt_s);

    DosingState state()          const noexcept { return state_; }
    double      accumulated_ml() const noexcept { return accumulated_ml_; }
    std::string active_tag()     const          { return active_tag_; }
    double      target_ml()      const noexcept { return target_volume_ml_; }
    void        reset()          noexcept;

private:
    DosingState state_{DosingState::IDLE};
    double      target_volume_ml_;
    double      accumulated_ml_{0.0};
    std::string active_tag_;
};
