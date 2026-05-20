#include "BatteryModel.h"
#include <cmath>

const char* fault_code_name(FaultCode f) noexcept {
    switch (f) {
        case FaultCode::NONE:            return "NONE";
        case FaultCode::OVERTEMPERATURE: return "OVERTEMPERATURE";
        case FaultCode::UNDERVOLTAGE:    return "UNDERVOLTAGE";
        case FaultCode::OVERVOLTAGE:     return "OVERVOLTAGE";
        case FaultCode::OVERCURRENT:     return "OVERCURRENT";
    }
    return "UNKNOWN";
}

BatteryModel::Deriv BatteryModel::derivatives(double soc, double v_rc,
                                               double t_cell, double i,
                                               bool block_cool) const noexcept {
    Deriv d;
    d.d_soc   = -ETA * i / (3600.0 * Q_NOM);
    d.d_v_rc  = -v_rc / (R1 * C1) + i / C1;
    double p_heat = i * i * R0;
    double p_cool = block_cool ? 0.0 : H_A * (t_cell - T_AMB);
    d.d_t_cell = (p_heat - p_cool) / M_CP;
    return d;
}

FaultCode BatteryModel::step(BatteryState& s) noexcept {
    const double i = s.i_load;

    // Overcurrent check (guard before integration)
    if (std::abs(i) > I_MAX) return FaultCode::OVERCURRENT;

    // RK4 integration
    auto k1 = derivatives(s.soc, s.v_rc, s.t_cell, i, s.block_cooling);

    double s2 = s.soc    + 0.5 * DT * k1.d_soc;
    double v2 = s.v_rc   + 0.5 * DT * k1.d_v_rc;
    double t2 = s.t_cell + 0.5 * DT * k1.d_t_cell;
    auto k2 = derivatives(s2, v2, t2, i, s.block_cooling);

    double s3 = s.soc    + 0.5 * DT * k2.d_soc;
    double v3 = s.v_rc   + 0.5 * DT * k2.d_v_rc;
    double t3 = s.t_cell + 0.5 * DT * k2.d_t_cell;
    auto k3 = derivatives(s3, v3, t3, i, s.block_cooling);

    double s4 = s.soc    + DT * k3.d_soc;
    double v4 = s.v_rc   + DT * k3.d_v_rc;
    double t4 = s.t_cell + DT * k3.d_t_cell;
    auto k4 = derivatives(s4, v4, t4, i, s.block_cooling);

    s.soc    += DT / 6.0 * (k1.d_soc   + 2*k2.d_soc   + 2*k3.d_soc   + k4.d_soc);
    s.v_rc   += DT / 6.0 * (k1.d_v_rc  + 2*k2.d_v_rc  + 2*k3.d_v_rc  + k4.d_v_rc);
    s.t_cell += DT / 6.0 * (k1.d_t_cell + 2*k2.d_t_cell + 2*k3.d_t_cell + k4.d_t_cell);

    // Clamp SoC
    if (s.soc < 0.0) s.soc = 0.0;
    if (s.soc > 1.0) s.soc = 1.0;

    // Update terminal voltage
    s.v_terminal = v_ocv(s.soc) - i * R0 - s.v_rc;

    // Safety checks
    if (s.t_cell > T_FAULT)        return FaultCode::OVERTEMPERATURE;
    if (s.soc < SOC_LOW)           return FaultCode::UNDERVOLTAGE;
    if (s.soc > SOC_HIGH && i < 0) return FaultCode::OVERVOLTAGE;

    return FaultCode::NONE;
}
