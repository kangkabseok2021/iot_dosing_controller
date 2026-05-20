#pragma once
#include <cstdint>

// Fault codes that the BMS can report.
enum class FaultCode : uint8_t {
    NONE,
    OVERTEMPERATURE,   // T_cell > 80 °C
    UNDERVOLTAGE,      // SoC < 0.05 (cell protection)
    OVERVOLTAGE,       // SoC > 0.95 during charging
    OVERCURRENT,       // |I| > 250 A
};

const char* fault_code_name(FaultCode f) noexcept;

// Battery telemetry snapshot — written by physics thread, read by TCP thread.
struct BatteryState {
    double soc{1.0};          // State of Charge [0, 1]
    double v_terminal{3.2};   // Terminal voltage [V]
    double v_rc{0.0};         // RC-branch voltage [V]
    double i_load{0.0};       // Load current [A] (positive = discharge)
    double t_cell{25.0};      // Cell temperature [°C]
    FaultCode fault{FaultCode::NONE};
    bool block_cooling{false}; // fault injection: simulate blocked cooling vent
};

// Thevenin 1-RC equivalent circuit model (LFP chemistry).
//
//  V_OCV(SoC) = 3.2 + 1.2·SoC          [V] — linear LFP open-circuit
//  V_terminal  = V_OCV − I·R0 − V_RC
//  dV_RC/dt    = −V_RC/(R1·C1) + I/C1   [V/s]
//  dSoC/dt     = −η·I / (3600·Q_nom)    [1/s]
//  dT/dt       = (I²·R0 − h·A·(T−T_amb)) / (m·cp)  [°C/s]
//
// Integrated by 4th-order Runge-Kutta at 1 kHz.
class BatteryModel {
public:
    // Physical constants
    static constexpr double R0         = 0.01;    // Ω — DC internal resistance
    static constexpr double R1         = 0.005;   // Ω — RC branch resistance
    static constexpr double C1         = 2000.0;  // F — RC branch capacitance
    static constexpr double Q_NOM      = 100.0;   // Ah
    static constexpr double ETA        = 0.98;    // Coulombic efficiency
    static constexpr double M_CP       = 25000.0; // J/K  (25 kg × 1000 J/kgK)
    static constexpr double H_A        = 10.0;    // W/K  (h=20 × A=0.5)
    static constexpr double T_AMB      = 25.0;    // °C
    static constexpr double I_MAX      = 250.0;   // A — overcurrent limit
    static constexpr double T_FAULT    = 80.0;    // °C — thermal runaway
    static constexpr double T_WARN     = 60.0;    // °C — thermal warning
    static constexpr double E_WARN     = 875.0;   // J  — cumulative Joule energy warning (I²R₀·Δt)
    static constexpr double E_FAULT    = 1375.0;  // J  — cumulative Joule energy fault (thermal runaway)
    static constexpr double SOC_LOW    = 0.05;    // undervoltage protection
    static constexpr double SOC_HIGH   = 0.95;    // overvoltage protection
    static constexpr double DT         = 1e-3;    // s — RK4 step (1 kHz)

    // Advance physics by one DT step.  Returns detected fault or NONE.
    FaultCode step(BatteryState& s) noexcept;

    static double v_ocv(double soc) noexcept { return 3.2 + 1.2 * soc; }

private:
    struct Deriv { double d_soc, d_v_rc, d_t_cell; };
    Deriv derivatives(double soc, double v_rc, double t_cell,
                      double i, bool block_cool) const noexcept;
};
