import math

class GribWarperEngine:
    def __init__(self):
        # Simulated raw 4x4 coordinate forecast grid ahead of the boat
        # Structure: (Latitude, Longitude) -> {"tws_forecast": knots, "twd_forecast": degrees}
        self.raw_grib_grid = {
            (35.0, -70.0): {"tws": 12.0, "twd": 90.0}, # Current boat position box
            (35.5, -69.5): {"tws": 13.0, "twd": 95.0},
            (36.0, -69.0): {"tws": 14.0, "twd": 100.0},
            (36.5, -68.5): {"tws": 15.0, "twd": 105.0}
        }

    def calculate_local_variance(self, live_telemetry):
        """Compares uncorrected GRIB data to real-world instrument vectors."""
        boat_coords = (35.0, -70.0) # Assume base grid match for local test
        base_forecast = self.raw_grib_grid[boat_coords]

        tws_delta = live_telemetry["true_wind_speed"] - base_forecast["tws"]
        twd_delta = live_telemetry["true_wind_angle"] - base_forecast["twd"] # Simplified relative to heading

        return tws_delta, twd_delta

    def generate_warped_grid(self, live_telemetry, decay_distance_nm=50.0):
        """
        Warps the future weather forecast matrix based on real instrument data.
        The correction is strong near the boat and decays smoothly to 0 further away.
        """
        tws_delta, twd_delta = self.calculate_local_variance(live_telemetry)
        boat_lat, boat_lon = 35.0, -70.0
        warped_grid = {}

        print(f"📊 Detected GRIB Discrepancy: TWS Delta: {tws_delta:+.1f} kts | TWD Delta: {twd_delta:+.1f}°")

        for coords, forecast in self.raw_grib_grid.items():
            # Calculate distance from the boat to the future node in Nautical Miles (approximate)
            lat_dist = (coords[0] - boat_lat) * 60.0
            lon_dist = (coords[1] - boat_lon) * 60.0 * math.cos(math.radians(boat_lat))
            distance = math.sqrt(lat_dist**2 + lon_dist**2)

            # Linear decay factor calculation (1.0 at boat, sliding to 0.0 at decay boundary)
            if distance >= decay_distance_nm:
                influence = 0.0
            else:
                influence = 1.0 - (distance / decay_distance_nm)

            # Apply weighted warp to the upcoming weather matrix
            warped_grid[coords] = {
                "tws": round(forecast["tws"] + (tws_delta * influence), 2),
                "twd": round((forecast["twd"] + (twd_delta * influence)) % 360, 1),
                "influence_applied": round(influence * 100, 1)
            }

        return warped_grid

if __name__ == "__main__":
    from loop1_replay import LogPlaybackSystem

    log_source = LogPlaybackSystem()
    warper = GribWarperEngine()

    # Simulate a loop iteration where instruments show a sudden weather shift/front arrival
    simulated_live_packet = {
        "true_wind_angle": 120.0, # Boat instruments measure 120
        "true_wind_speed": 17.5,   # Boat instruments measure 17.5 kts (GRIB says 12)
        "speed_through_water": 8.0,
        "sog": 8.2, "cog": 115.0
    }

    result_grid = warper.generate_warped_grid(simulated_live_packet)

    print("\n🗺️ COMPUTE OUTCOME: Adjusted Weather Matrix for Next Leg:")
    for loc, data in result_grid.items():
        print(f"Node {loc} ({int(loc[0]*60 - 35*60)}nm ahead) -> Adjusted Wind: {data['tws']}kts @ {data['twd']}° [Warp Weight: {data['influence_applied']}%]")
