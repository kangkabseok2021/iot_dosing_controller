#include <gtest/gtest.h>
#include "../src/DosingFsm.h"
#include "../src/FlowSensor.h"
#include "../src/RfidSimulator.h"
#include <optional>

// ── RfidSimulator ─────────────────────────────────────────────────────────

TEST(RfidSimulatorTest, PoolHasCorrectSize) {
    RfidSimulator sim(42, 5);
    EXPECT_EQ(sim.pool().size(), 5u);
}

TEST(RfidSimulatorTest, EpcIs16Chars) {
    RfidSimulator sim;
    for (const auto& epc : sim.pool())
        EXPECT_EQ(epc.size(), 16u);
}

TEST(RfidSimulatorTest, InjectTagReturnedOnNextScan) {
    RfidSimulator sim;
    sim.inject("AABBCCDD11223344");
    auto tag = sim.scan();
    ASSERT_TRUE(tag.has_value());
    EXPECT_EQ(tag->epc, "AABBCCDD11223344");
}

TEST(RfidSimulatorTest, InjectedTagClearedAfterOneScan) {
    RfidSimulator sim;
    sim.inject("AABBCCDD11223344");
    sim.scan();  // consume injection
    // Next scan has normal (non-injected) behaviour — cannot guarantee result,
    // but inject must not fire twice.
    for (int i = 0; i < 20; ++i) {
        auto t = sim.scan();
        if (t) EXPECT_NE(t->epc, "AABBCCDD11223344");
    }
}

// ── FlowSensor ────────────────────────────────────────────────────────────

TEST(FlowSensorTest, ZeroTargetProducesLowFlow) {
    FlowSensor fs;
    auto r = fs.read(0.0);
    EXPECT_LT(r.flow_rate_ml_min, FlowSensor::LOW_THRESHOLD_ML_MIN);
    EXPECT_FALSE(r.is_flowing);
}

TEST(FlowSensorTest, NominalTargetIsFlowing) {
    FlowSensor fs;
    auto r = fs.read(200.0);
    EXPECT_GT(r.flow_rate_ml_min, FlowSensor::LOW_THRESHOLD_ML_MIN);
    EXPECT_TRUE(r.is_flowing);
}

// ── DosingFsm ─────────────────────────────────────────────────────────────

static FlowReading flowing()     { return {200.0, 40.0, true}; }
static FlowReading not_flowing() { return {0.0,   0.0,  false}; }
static std::optional<RfidTag> make_tag() {
    return RfidTag{"AABBCCDD11223344", "s1", 0};
}

TEST(DosingFsmTest, StartsIdle) {
    DosingFsm fsm;
    EXPECT_EQ(fsm.state(), DosingState::IDLE);
}

TEST(DosingFsmTest, IdleToDosingOnValveAndRfid) {
    DosingFsm fsm;
    fsm.update(true, false, flowing(), make_tag(), 0.1);
    EXPECT_EQ(fsm.state(), DosingState::DOSING);
}

TEST(DosingFsmTest, IdleStaysIdleWithoutRfid) {
    DosingFsm fsm;
    fsm.update(true, false, flowing(), std::nullopt, 0.1);
    EXPECT_EQ(fsm.state(), DosingState::IDLE);
}

TEST(DosingFsmTest, DosingToPauseOnValveClose) {
    DosingFsm fsm;
    fsm.update(true,  false, flowing(), make_tag(), 0.1);
    fsm.update(false, false, flowing(), std::nullopt, 0.1);
    EXPECT_EQ(fsm.state(), DosingState::PAUSE);
}

TEST(DosingFsmTest, AccumulatesVolumeWhileDosing) {
    DosingFsm fsm(10000.0);   // large target so we don't complete
    fsm.update(true, false, flowing(), make_tag(), 0.1);  // → DOSING
    fsm.update(true, false, flowing(), std::nullopt, 60.0);  // 1 min at 200 ml/min = 200 ml
    EXPECT_NEAR(fsm.accumulated_ml(), 200.0 + 200.0 * (0.1 / 60.0), 5.0);
}

TEST(DosingFsmTest, CompletesWhenTargetReached) {
    DosingFsm fsm(10.0);   // tiny target — 10 ml
    fsm.update(true, false, flowing(), make_tag(), 0.1);
    // 200 ml/min for 60 s = 200 ml >> 10 ml target
    fsm.update(true, false, flowing(), std::nullopt, 60.0);
    EXPECT_EQ(fsm.state(), DosingState::COMPLETE);
}

TEST(DosingFsmTest, ResetFromComplete) {
    DosingFsm fsm(10.0);
    fsm.update(true, false, flowing(), make_tag(), 0.1);
    fsm.update(true, false, flowing(), std::nullopt, 60.0);
    ASSERT_EQ(fsm.state(), DosingState::COMPLETE);
    fsm.update(false, true, not_flowing(), std::nullopt, 0.1);  // reset_cmd=1
    EXPECT_EQ(fsm.state(), DosingState::IDLE);
    EXPECT_DOUBLE_EQ(fsm.accumulated_ml(), 0.0);
}
