"""Loop 2: Storm Performance Matrix

Evaluates live telemetry against Second Storm's polar chart to determine
target boat speed and how efficiently the boat is sailing relative to it.
"""

# Polar chart: target boat speed (knots) indexed by true wind speed (TWS)
# and true wind angle (TWA). Values are bilinearly interpolated between
# the nearest breakpoints on both axes.
TWS_BREAKPOINTS = [6, 8, 10, 12, 14, 16, 20, 24, 30]
TWA_BREAKPOINTS = [40, 50, 60, 70, 80, 90, 100, 110, 120, 135, 150, 165, 180]

POLAR_TABLE = [
    # 40    50    60    70    80    90   100   110   120   135   150   165   180
    [4.8, 5.6, 6.1, 6.3, 6.3, 6.2, 6.1, 6.0, 5.8, 5.4, 4.9, 4.5, 4.3],   # TWS  6
    [5.6, 6.4, 6.9, 7.1, 7.2, 7.1, 7.0, 6.9, 6.7, 6.3, 5.7, 5.2, 5.0],   # TWS  8
    [6.2, 6.9, 7.4, 7.7, 7.8, 7.7, 7.6, 7.5, 7.3, 6.9, 6.3, 5.7, 5.5],   # TWS 10
    [6.5, 7.2, 7.7, 8.0, 8.1, 8.1, 8.0, 7.9, 7.7, 7.3, 6.7, 6.1, 5.8],   # TWS 12
    [6.7, 7.4, 7.9, 8.2, 8.4, 8.4, 8.3, 8.2, 8.0, 7.6, 7.0, 6.4, 6.1],   # TWS 14
    [6.8, 7.5, 8.1, 8.4, 8.6, 8.7, 8.7, 8.6, 8.4, 8.0, 7.4, 6.7, 6.4],   # TWS 16
    [6.9, 7.6, 8.3, 8.7, 9.0, 9.2, 9.2, 9.1, 8.9, 8.6, 8.0, 7.3, 6.9],   # TWS 20
    [7.0, 7.7, 8.4, 8.9, 9.2, 9.4, 9.5, 9.4, 9.3, 9.0, 8.4, 7.7, 7.3],   # TWS 24
    [7.0, 7.7, 8.4, 9.0, 9.3, 9.6, 9.7, 9.7, 9.6, 9.3, 8.8, 8.1, 7.7],   # TWS 30
]


def _clamp_index(value, breakpoints):
    """Return the (lo_idx, hi_idx, fraction) straddling `value` in `breakpoints`."""
    if value <= breakpoints[0]:
        return 0, 0, 0.0
    if value >= breakpoints[-1]:
        last = len(breakpoints) - 1
        return last, last, 0.0
    for i in range(len(breakpoints) - 1):
        lo, hi = breakpoints[i], breakpoints[i + 1]
        if lo <= value <= hi:
            fraction = (value - lo) / (hi - lo)
            return i, i + 1, fraction
    return 0, 0, 0.0


def _lerp(a, b, fraction):
    return a + (b - a) * fraction


class SecondStormMatrix:
    """Looks up target boat speed on Second Storm's polar chart and scores efficiency."""

    def __init__(self, polar_table=POLAR_TABLE, tws_breakpoints=TWS_BREAKPOINTS,
                 twa_breakpoints=TWA_BREAKPOINTS):
        self.polar_table = polar_table
        self.tws_breakpoints = tws_breakpoints
        self.twa_breakpoints = twa_breakpoints

    def _target_boat_speed(self, twa, tws):
        twa = abs(twa)
        tws_lo, tws_hi, tws_frac = _clamp_index(tws, self.tws_breakpoints)
        twa_lo, twa_hi, twa_frac = _clamp_index(twa, self.twa_breakpoints)

        row_lo = self.polar_table[tws_lo]
        row_hi = self.polar_table[tws_hi]

        speed_at_tws_lo = _lerp(row_lo[twa_lo], row_lo[twa_hi], twa_frac)
        speed_at_tws_hi = _lerp(row_hi[twa_lo], row_hi[twa_hi], twa_frac)

        return _lerp(speed_at_tws_lo, speed_at_tws_hi, tws_frac)

    def evaluate_performance(self, twa, tws, stw):
        target_btv = round(self._target_boat_speed(twa, tws), 2)
        polar_eff = round((stw / target_btv) * 100.0, 1) if target_btv else 0.0
        return target_btv, polar_eff


if __name__ == "__main__":
    matrix = SecondStormMatrix()
    print("Running Loop 2 Validation: Scoring telemetry against the polar chart...")
    sample_packets = [
        {"twa": 60.0, "tws": 12.0, "stw": 6.99},
        {"twa": 70.0, "tws": 14.0, "stw": 7.73},
        {"twa": 110.0, "tws": 16.0, "stw": 8.76},
        {"twa": 135.0, "tws": 20.0, "stw": 8.82},
    ]
    for packet in sample_packets:
        target, efficiency = matrix.evaluate_performance(packet["twa"], packet["tws"], packet["stw"])
        print(f"TWA {packet['twa']} / TWS {packet['tws']} -> target {target} kts, "
              f"actual {packet['stw']} kts, efficiency {efficiency}%")
