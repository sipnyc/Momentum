class CurrentIngestionEngine:
    def __init__(self):
        print("🌊 Gulf Stream Current Vector Layer Ready.")

    def get_current_vector(self, lat, lon):
        """Returns current speed (knots) and flow direction (degrees)."""
        # Simulate Gulf Stream core boundaries
        if 34.0 <= lat <= 36.0 and -73.0 <= lon <= -70.0:
            return 4.2, 055.0 # Heavy northeast push
        return 0.5, 180.0
