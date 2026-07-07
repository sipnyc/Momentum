import pandas as pd
import numpy as np
from scipy.interpolate import RectBivariateSpline
from loop1_replay import LogPlaybackSystem

class SecondStormMatrix:
    def __init__(self):
        # Exact True Wind Speeds and Angles from Second Storm's Speed Guide
        self.twa_axis = np.array([60.0, 70.0, 75.0, 80.0, 90.0, 110.0, 120.0, 135.0, 150.0, 165.0, 180.0])
        self.tws_axis = np.array([12.0, 14.0, 16.0, 20.0])

        # Grid layout matching target data arrays [TWA x TWS]
        # Columns mapped to: 12kts, 14kts, 16kts, 20kts wind bands
        self.btv_grid = np.array([
            [6.99, 7.16, 6.64, 6.28],  # 60° TWA
            [7.54, 7.73, 7.54, 7.54],  # 70°
            [7.72, 7.92, 7.81, 7.86],  # 75°
            [7.86, 8.07, 8.02, 8.11],  # 80°
            [8.08, 8.31, 8.37, 8.53],  # 90°
            [8.14, 8.46, 8.76, 9.11],  # 110°
            [8.03, 8.39, 8.77, 9.29],  # 120°
            [7.54, 8.02, 8.57, 9.16],  # 135°
            [7.04, 6.38, 8.11, 8.67],  # 150°
            [6.37, 5.67, 7.26, 8.13],  # 165°
            [5.33, 6.03, 6.67, 7.71]   # 180°
        ])

        # Generate our analytical 2D spline
        self.spline = RectBivariateSpline(self.twa_axis, self.tws_axis, self.btv_grid, kx=3, ky=3)

    def evaluate_performance(self, twa, tws, stw):
        twa_clamped = np.clip(abs(twa), self.twa_axis.min(), self.twa_axis.max())
        tws_clamped = np.clip(tws, self.tws_axis.min(), self.tws_axis.max())

        target_speed = float(self.spline(twa_clamped, tws_clamped)[0][0])
        efficiency = (stw / target_speed) * 100 if target_speed > 0 else 0.0
        return round(target_speed, 2), round(efficiency, 1)

if __name__ == "__main__":
    log_source = LogPlaybackSystem()
    analyzer = SecondStormMatrix()
    print("📈 Running Loop 2 Validation: Extracting true polar variances...")
    for _ in range(4):
        data = log_source.pull_live_packet()
        target, eff = analyzer.evaluate_performance(data["twa"], data["tws"], data["stw"])
        print(f"TWA: {data['twa']}° | TWS: {data['tws']}kt | Actual: {data['stw']}kt | Target BTV: {target}kt | Efficiency: {eff}%")
