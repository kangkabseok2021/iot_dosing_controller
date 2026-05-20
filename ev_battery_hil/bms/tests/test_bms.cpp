#include "../src/BatteryModel.h"
#include "../src/BmsStateMachine.h"
#include <gtest/gtest.h>
#include <cmath>

// ── Helpers ───────────────────────────────────────────────────────────────────

static BatteryState make_state(double soc = 0.8, double i = 0.0, double t = 25.0,
                                bool block_cool = false) {
    BatteryState s;
    s.soc           = soc;
    s.i_load        = i;
    s.t_cell        = t;
    s.v_rc          = 0.0;
    s.block_cooling = block_cool;
    s.v_terminal    = BatteryModel::v_ocv(soc) - i * BatteryModel::R0;
    return s;
}

static BatteryState run_steps(BmsStateMachine& fsm, BatteryState s, int steps) {
    for (int i = 0; i < steps; ++i) fsm.update(s);
    return s;
}

// ── BatteryModelTest (4) ──────────────────────────────────────────────────────

TEST(BatteryModelTest, SoCDecreasesUnderLoad) {
    BmsStateMachine fsm;
    auto s = make_state(0.5, 50.0);
    double soc0 = s.soc;
    s = run_steps(fsm, s, 1000);
    EXPECT_LT(s.soc, soc0) << "SoC must decrease during discharge";
}

TEST(BatteryModelTest, VoltageSagMatchesThevenin) {
    BmsStateMachine fsm;
    auto s = make_state(0.5, 50.0);
    s = run_steps(fsm, s, 50000);
    double v_oc       = BatteryModel::v_ocv(s.soc);
    double v_expected = v_oc - 50.0 * BatteryModel::R0 - 50.0 * BatteryModel::R1;
    EXPECT_NEAR(s.v_terminal, v_expected, 0.02)
        << "Terminal voltage must match Thevenin steady-state";
}

TEST(BatteryModelTest, ThermalRisesUnderJouleHeating) {
    BmsStateMachine fsm;
    auto s = make_state(0.8, 200.0, 25.0, /*block_cool=*/true);
    double t0 = s.t_cell;
    s = run_steps(fsm, s, 5000);
    EXPECT_GT(s.t_cell, t0 + 0.05) << "Temperature must rise under Joule heating";
}

TEST(BatteryModelTest, RK4AccuracyVsEuler) {
    BmsStateMachine fsm;
    auto s = make_state(0.8, 50.0, 25.0);
    s = run_steps(fsm, s, 1000);
    EXPECT_NEAR(s.t_cell, 25.001, 0.01) << "RK4 thermal integration must be accurate";
}

// ── BmsStateMachineTest (7) ───────────────────────────────────────────────────

TEST(BmsStateMachineTest, IdleToDischarging) {
    BmsStateMachine fsm;
    auto s = make_state(0.8, 50.0);
    fsm.update(s);
    EXPECT_EQ(fsm.state(), BmsState::DISCHARGING);
}

TEST(BmsStateMachineTest, FaultOnOvertemperature) {
    BmsStateMachine fsm;
    auto s = make_state(0.8, 200.0, 79.9, /*block_cool=*/true);
    for (int i = 0; i < 10000 && fsm.state() != BmsState::FAULT; ++i) fsm.update(s);
    EXPECT_EQ(fsm.state(), BmsState::FAULT);
    EXPECT_EQ(fsm.fault_code(), FaultCode::OVERTEMPERATURE);
}

TEST(BmsStateMachineTest, FaultLatches) {
    BmsStateMachine fsm;
    auto s = make_state(0.8, 200.0, 79.9, /*block_cool=*/true);
    for (int i = 0; i < 10000 && fsm.state() != BmsState::FAULT; ++i) fsm.update(s);
    ASSERT_EQ(fsm.state(), BmsState::FAULT);
    s.i_load = 0.0; s.t_cell = 25.0;
    for (int i = 0; i < 1000; ++i) fsm.update(s);
    EXPECT_EQ(fsm.state(), BmsState::FAULT) << "FAULT must latch until reset()";
}

TEST(BmsStateMachineTest, ResetFromFault) {
    BmsStateMachine fsm;
    auto s = make_state(0.8, 200.0, 79.9, /*block_cool=*/true);
    for (int i = 0; i < 10000 && fsm.state() != BmsState::FAULT; ++i) fsm.update(s);
    ASSERT_EQ(fsm.state(), BmsState::FAULT);
    fsm.reset(s);
    EXPECT_EQ(fsm.state(), BmsState::IDLE);
    EXPECT_EQ(fsm.fault_code(), FaultCode::NONE);
}

TEST(BmsStateMachineTest, OvercurrentRejected) {
    BmsStateMachine fsm;
    auto s = make_state(0.8, 300.0);
    bool ok = fsm.update(s);
    EXPECT_FALSE(ok) << "SET_CURRENT 300 A must be rejected";
    EXPECT_EQ(fsm.state(), BmsState::FAULT);
    EXPECT_EQ(fsm.fault_code(), FaultCode::OVERCURRENT);
}

TEST(BmsStateMachineTest, SocUndervoltageTriggersProtection) {
    BmsStateMachine fsm;
    auto s = make_state(0.051, 50.0);
    for (int i = 0; i < 10000 && fsm.state() != BmsState::FAULT; ++i) fsm.update(s);
    EXPECT_EQ(fsm.state(), BmsState::FAULT);
    EXPECT_EQ(fsm.fault_code(), FaultCode::UNDERVOLTAGE);
}

TEST(BmsStateMachineTest, WarnFiresBeforeFaultOnThermalRunaway) {
    // I=50A, block_cool=true: P_heat=25W, P_cool=0
    // Thermal rise: dT/step=25×1e-3/25000=0.000001°C — T_WARN unreachable in 200k steps.
    // WARN fires via energy accumulator: E=I²·R0·DT=0.025J/step → E_WARN=875J at ~35000 steps.
    // FAULT fires via energy accumulator: E_FAULT=1375J at ~55000 steps.
    BmsStateMachine fsm;
    auto s = make_state(0.8, 50.0, 25.0, /*block_cool=*/true);
    int warned_step = -1;
    for (int i = 0; i < 200'000; ++i) {
        fsm.update(s);
        if (warned_step < 0 && fsm.warned()) warned_step = i;
        if (fsm.state() == BmsState::FAULT) {
            EXPECT_GT(warned_step, 0) << "WARN must have fired before FAULT";
            EXPECT_LT(warned_step, i) << "WARN step must precede FAULT step";
            return;
        }
    }
    FAIL() << "FAULT never triggered within 200k steps";
}
