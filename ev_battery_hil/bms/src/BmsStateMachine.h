#pragma once
#include "BatteryModel.h"
#include <cstdint>
#include <string>

enum class BmsState : uint8_t { IDLE, DISCHARGING, CHARGING, FAULT };

const char* bms_state_name(BmsState s) noexcept;

// Four-state BMS FSM mirroring production BMS firmware logic.
//   IDLE        → DISCHARGING   when I > 5 A
//   IDLE        → CHARGING      when I < −5 A
//   DISCHARGING → IDLE          when I ≤ 5 A
//   DISCHARGING → FAULT         on any safety threshold breach
//   CHARGING    → IDLE          when I ≥ −5 A
//   CHARGING    → FAULT         on overvoltage or overtemperature
//   FAULT       → IDLE          only via explicit reset()
class BmsStateMachine {
public:
    static constexpr double kIdleThreshold = 5.0;  // A

    // Drive one update cycle.  Integrates the battery model one step,
    // evaluates safety guards, and advances FSM state.
    // Returns false if current was rejected (overcurrent).
    bool update(BatteryState& s);

    void reset(BatteryState& s) noexcept;

    BmsState state()      const noexcept { return state_; }
    FaultCode fault_code() const noexcept { return fault_code_; }
    std::string fault_detail() const { return fault_detail_; }

private:
    BatteryModel model_;
    BmsState     state_{BmsState::IDLE};
    FaultCode    fault_code_{FaultCode::NONE};
    std::string  fault_detail_;

    void enter_fault(FaultCode fc, const BatteryState& s) noexcept;
};
