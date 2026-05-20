#include "BmsStateMachine.h"
#include <cstdio>

const char* bms_state_name(BmsState s) noexcept {
    switch (s) {
        case BmsState::IDLE:        return "IDLE";
        case BmsState::DISCHARGING: return "DISCHARGING";
        case BmsState::CHARGING:    return "CHARGING";
        case BmsState::FAULT:       return "FAULT";
    }
    return "UNKNOWN";
}

void BmsStateMachine::enter_fault(FaultCode fc, const BatteryState& s) noexcept {
    state_      = BmsState::FAULT;
    fault_code_ = fc;
    char buf[128];
    std::snprintf(buf, sizeof(buf),
        "FAULT: %s  SoC=%.3f  T=%.1f°C  V=%.3fV  I=%.1fA",
        fault_code_name(fc), s.soc, s.t_cell, s.v_terminal, s.i_load);
    fault_detail_ = buf;
}

bool BmsStateMachine::update(BatteryState& s) {
    if (state_ == BmsState::FAULT) return true;  // latched

    // Overcurrent: reject command, do not integrate
    if (std::abs(s.i_load) > BatteryModel::I_MAX) {
        enter_fault(FaultCode::OVERCURRENT, s);
        return false;
    }

    FaultCode fc = model_.step(s);  // s.i_load is read-only in model_.step()

    // Accumulate Joule heating energy (I²·R₀·Δt) for thermal runaway detection
    joule_energy_ += s.i_load * s.i_load * BatteryModel::R0 * BatteryModel::DT;

    // Temperature-based warning
    if (!warned_ && s.t_cell >= BatteryModel::T_WARN) {
        warned_ = true;
        fprintf(stderr, "[WARN] T_cell=%.1f>=%.0f°C — thermal warning threshold\n",
                s.t_cell, BatteryModel::T_WARN);
    }
    // Cumulative energy-based warning (fires before energy fault)
    if (!warned_ && joule_energy_ >= BatteryModel::E_WARN) {
        warned_ = true;
        fprintf(stderr, "[WARN] Joule energy=%.0fJ>=%.0fJ — thermal runaway risk\n",
                joule_energy_, BatteryModel::E_WARN);
    }

    // Model-level fault (overtemperature, undervoltage, overvoltage)
    if (fc != FaultCode::NONE) {
        enter_fault(fc, s);
        return true;
    }

    // Energy-based thermal runaway fault
    if (joule_energy_ >= BatteryModel::E_FAULT) {
        enter_fault(FaultCode::OVERTEMPERATURE, s);
        return true;
    }

    s.fault = FaultCode::NONE;

    // FSM transitions
    const double i = s.i_load;
    switch (state_) {
        case BmsState::IDLE:
            if (i > kIdleThreshold)  state_ = BmsState::DISCHARGING;
            else if (i < -kIdleThreshold) state_ = BmsState::CHARGING;
            break;
        case BmsState::DISCHARGING:
            if (i <= kIdleThreshold) state_ = BmsState::IDLE;
            break;
        case BmsState::CHARGING:
            if (i >= -kIdleThreshold) state_ = BmsState::IDLE;
            break;
        case BmsState::FAULT:
            break;
    }
    return true;
}

void BmsStateMachine::reset(BatteryState& s) noexcept {
    state_       = BmsState::IDLE;
    fault_code_  = FaultCode::NONE;
    fault_detail_.clear();
    warned_         = false;
    joule_energy_   = 0.0;
    s.fault         = FaultCode::NONE;
    s.block_cooling = false;
    s.i_load        = 0.0;
}
