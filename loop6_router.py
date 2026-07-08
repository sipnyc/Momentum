import math
import numpy as np
from loop2_analyzer import SecondStormMatrix

class IsochroneSolver:
    def __init__(self, destination_lat=32.3, destination_lon=-64.8):
        self.matrix = SecondStormMatrix()
        self.dest_lat = destination_lat
        self.dest_lon = destination_lon

    def project_isochrone_node(self, start_lat, start_lon, heading, tws, twd, current_speed, current_dir):
        """Calculates a single forward node step factoring in polars and current vectors."""
        twa = (heading - twd) % 360
        
        # 1. Fetch performance profile from Second Storm's polar spline
        target_speed, _ = self.matrix.evaluate_performance(twa, tws, stw=0.0)
        
        # 2. Apply Wind-Over-Current Wave Penalty Logic
        if tws > 25.0 and abs((twd - current_dir) % 360) > 135:
            target_speed *= 0.85 # 15% structural speed penalty for square wave resistance
            
        # 3. Calculate Boat Speed Vector Components (Nautical Miles per Hour)
        boat_vx = target_speed * math.sin(math.radians(heading))
        boat_vy = target_speed * math.cos(math.radians(heading))
        
        # 4. Calculate Ocean Current Vector Components
        current_vx = current_speed * math.sin(math.radians(current_dir))
        current_vy = current_speed * math.cos(math.radians(current_dir))
        
        # 5. Vector Addition: Speed Over Ground (SOG) vector
        sog_vx = boat_vx + current_vx
        sog_vy = boat_vy + current_vy
        
        delta_time = 0.25 # 15 minute increments
        delta_lat = (sog_vy * delta_time) / 60.0
        delta_lon = (sog_vx * delta_time) / (60.0 * math.cos(math.radians(start_lat)))
        
        return start_lat + delta_lat, start_lon + delta_lon

if __name__ == "__main__":
    solver = IsochroneSolver()
    # Quick test node projection
    next_lat, next_lon = solver.project_isochrone_node(35.0, -70.0, 120.0, 14.0, 90.0, 2.0, 45.0)
    print(f"🧭 Loop 6 Test Vector: Projected Next Position -> Lat: {next_lat:.4f}, Lon: {next_lon:.4f}")
