"""Loop 2: Storm Performance Matrix

Evaluates live telemetry against Second Storm's ORC Speed Guide to determine
target boat speed, heel, reef, and flattening configuration, and how
efficiently the boat is sailing relative to target boat speed.
"""

import numpy as np
from scipy.interpolate import RectBivariateSpline


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
    matrix = SecondStormCompleteMatrix()
    print("Running Loop 2 Validation: Scoring telemetry against the full ORC deck-state matrix...")
    sample_packets = [
        {"twa": 60.0, "tws": 12.0, "stw": 6.99},
        {"twa": 70.0, "tws": 14.0, "stw": 7.73},
        {"twa": 110.0, "tws": 16.0, "stw": 8.76},
        {"twa": 135.0, "tws": 20.0, "stw": 8.82},
    ]
    for packet in sample_packets:
        state = matrix.analyze_deck_state(packet["twa"], packet["tws"], packet["stw"])
        print(f"TWA {packet['twa']} / TWS {packet['tws']} -> target {state['target_btv']} kts, "
              f"actual {packet['stw']} kts, efficiency {state['efficiency_pct']}%, "
              f"heel {state['target_heel']}°, reef {state['target_reef']}, flat {state['target_flat']}")
