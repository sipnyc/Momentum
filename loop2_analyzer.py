"""Loop 2: Storm Performance Matrix

Evaluates live telemetry against Second Storm's polar chart to determine
target boat speed and how efficiently the boat is sailing relative to it.
"""

import numpy as np
from scipy.interpolate import RectBivariateSpline

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


class SecondStormCompleteMatrix:
    """Looks up Second Storm's full ORC target state (BTV, heel, reef, flat)
    for a given true wind angle/speed and scores boat speed efficiency.

    Uses linear (kx=1, ky=1) RectBivariateSpline fits rather than the bicubic
    fit an earlier version used: the TWS axis has only 4 points and two TWA
    rows dip non-monotonically across them, so a degree-3 fit overshoots past
    the input data's own range (e.g. a reef fraction of 1.028, >100% sail
    area, at TWA~74.5deg/TWS~12.9kt). Linear keeps every query bounded by the
    surrounding grid points.
    """

    def __init__(self):
        self.twa_axis = np.array([60.0, 70.0, 75.0, 80.0, 90.0, 110.0, 120.0, 135.0, 150.0, 165.0, 180.0])
        self.tws_axis = np.array([12.0, 14.0, 16.0, 20.0])

        self.btv_grid = np.array([
            [6.99, 7.16, 6.64, 6.28],  # 60 deg TWA
            [7.54, 7.73, 7.54, 7.54],  # 70
            [7.72, 7.92, 7.81, 7.86],  # 75
            [7.86, 8.07, 8.02, 8.11],  # 80
            [8.08, 8.31, 8.37, 8.53],  # 90
            [8.14, 8.46, 8.76, 9.11],  # 110
            [8.03, 8.39, 8.77, 9.29],  # 120
            [7.54, 8.02, 8.57, 9.16],  # 135
            [7.04, 6.38, 8.11, 8.67],  # 150
            [6.37, 5.67, 7.26, 8.13],  # 165
            [5.33, 6.03, 6.67, 7.71],  # 180
        ])
        self.heel_grid = np.array([
            [22.5, 24.2, 21.7, 24.7],  # 60 deg TWA
            [22.4, 26.8, 22.0, 23.2],  # 70
            [21.7, 27.2, 21.9, 23.0],  # 75
            [20.6, 26.0, 22.0, 22.8],  # 80
            [18.0, 22.4, 21.9, 22.5],  # 90
            [10.3, 13.5, 18.7, 22.0],  # 110
            [6.1,  8.2,  12.3, 18.1],  # 120
            [1.0,  2.0,  4.5,  7.6],   # 135
            [1.8,  1.7,  1.1,  1.3],   # 150
            [3.7,  3.5,  3.5,  3.3],   # 165
            [3.0,  3.0,  3.1,  3.2],   # 180
        ])
        self.reef_grid = np.array([
            [1.00, 0.95, 0.87, 0.91],  # 60 deg TWA
            [1.00, 0.98, 0.86, 0.85],  # 70
            [1.00, 1.00, 0.86, 0.85],  # 75
            [1.00, 1.00, 0.94, 0.85],  # 80
            [1.00, 1.00, 0.94, 0.85],  # 90
            [1.00, 1.00, 1.00, 0.97],  # 110
            [1.00, 1.00, 1.00, 1.00],  # 120
            [1.00, 1.00, 1.00, 1.00],  # 135
            [1.00, 1.00, 1.00, 1.00],  # 150
            [1.00, 1.00, 1.00, 1.00],  # 165
            [1.00, 1.00, 1.00, 1.00],  # 180
        ])
        self.flat_grid = np.array([
            [0.93, 0.91, 0.93, 0.61],  # 60 deg TWA
            [0.94, 0.92, 0.94, 0.69],  # 70
            [0.95, 0.93, 0.94, 0.69],  # 75
            [0.95, 0.94, 0.87, 0.71],  # 80
            [0.97, 0.95, 0.91, 0.82],  # 90
            [1.00, 1.00, 1.00, 0.95],  # 110
            [1.00, 1.00, 1.00, 1.00],  # 120
            [1.00, 1.00, 1.00, 1.00],  # 135
            [1.00, 1.00, 1.00, 1.00],  # 150
            [1.00, 1.00, 1.00, 1.00],  # 165
            [1.00, 1.00, 1.00, 1.00],  # 180
        ])

        self.btv_spline = RectBivariateSpline(self.twa_axis, self.tws_axis, self.btv_grid, kx=1, ky=1)
        self.heel_spline = RectBivariateSpline(self.twa_axis, self.tws_axis, self.heel_grid, kx=1, ky=1)
        self.reef_spline = RectBivariateSpline(self.twa_axis, self.tws_axis, self.reef_grid, kx=1, ky=1)
        self.flat_spline = RectBivariateSpline(self.twa_axis, self.tws_axis, self.flat_grid, kx=1, ky=1)

    def analyze_deck_state(self, twa, tws, stw):
        twa_clamped = np.clip(abs(twa), self.twa_axis.min(), self.twa_axis.max())
        tws_clamped = np.clip(tws, self.tws_axis.min(), self.tws_axis.max())

        target_speed = float(self.btv_spline(twa_clamped, tws_clamped)[0][0])
        efficiency = (stw / target_speed) * 100 if target_speed > 0 else 0.0

        return {
            "target_btv": round(target_speed, 2),
            "efficiency_pct": round(efficiency, 1),
            "target_heel": round(float(self.heel_spline(twa_clamped, tws_clamped)[0][0]), 1),
            "target_reef": round(float(self.reef_spline(twa_clamped, tws_clamped)[0][0]), 2),
            "target_flat": round(float(self.flat_spline(twa_clamped, tws_clamped)[0][0]), 2),
        }

    def evaluate_performance(self, twa, tws, stw):
        """Back-compat entry point for callers that only need target boat
        speed and efficiency (e.g. loop3_router.py, loop5_dashboard.py)."""
        deck_state = self.analyze_deck_state(twa, tws, stw)
        return deck_state["target_btv"], deck_state["efficiency_pct"]


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
