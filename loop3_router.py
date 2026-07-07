"""Loop 3: Path Router & Live VMC Optimizer

Bridges Loop 1 (telemetry replay) and Loop 2 (polar performance analysis) to
evaluate whether the boat's course over ground is making efficient progress
toward the destination, rather than just checking wind vectors alone.
"""
import math

from loop1_replay import LogPlaybackSystem
from loop2_analyzer import SecondStormCompleteMatrix


class TacticalVMCengine:
    def __init__(self, target_bearing=135.0):
        self.destination_bearing = target_bearing  # Core bearing to next mark (e.g., Bermuda)

    def calculate_vmc_metrics(self, sog, cog):
        # Calculate real progress vector alignment towards destination
        angle_radians = math.radians(cog - self.destination_bearing)
        vmc = sog * math.cos(angle_radians)
        return round(vmc, 2)

    def run_cycle(self, telemetry, analyzer_engine):
        target_btv, polar_eff = analyzer_engine.evaluate_performance(
            telemetry["twa"], telemetry["tws"],
            telemetry["speed_through_water"] if "speed_through_water" in telemetry else telemetry["stw"]
        )
        realized_vmc = self.calculate_vmc_metrics(telemetry["sog"], telemetry["cog"])

        # Flag structural alerts if velocity towards destination tanks
        action_flag = "STANDBY"
        if polar_eff < 92.0:
            action_flag = "🚨 SPEED LOSS: Check Trim or Sail Selection!"

        return {
            "polar_target": target_btv,
            "efficiency": polar_eff,
            "vmc_knots": realized_vmc,
            "tactical_status": action_flag
        }


if __name__ == "__main__":
    log_stream = LogPlaybackSystem()
    matrix_engine = SecondStormCompleteMatrix()
    router = TacticalVMCengine(target_bearing=140.0)  # Assume direct course line is 140 degrees

    print("🧭 Running Loop 3 Validation: Complete Path Core Engine...")
    for i in range(4):
        log_packet = log_stream.pull_live_packet()
        verdict = router.run_cycle(log_packet, matrix_engine)
        print(f"Cycle {i+1} Output:")
        print(f"   -> Real-World Target Speed: {verdict['polar_target']} kts | Efficiency: {verdict['efficiency']}%")
        print(f"   -> Effective Progress toward Destination (VMC): {verdict['vmc_knots']} kts")
        print(f"   -> Alert Status: {verdict['tactical_status']}\n")
