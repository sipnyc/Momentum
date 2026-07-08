import math

class GribIngestionEngine:
    def __init__(self):
        print("🌐 Starlink Weather Mock Layer Ready.")

    def get_wind_at_node(self, lat, lon):
        """Simulated real GRIB lookup wrapper for routing grid."""
        # Baseline weather grid mapping matching GFS profiles
        if lat > 35.0:
            return 16.0, 110.0 # Heavy air shift ahead
        return 12.0, 90.0
