"""Loop 8: Ocean Current Ingestion

Fetches an open-source ocean current velocity grid (NOAA RTOFS) over our
bounding box (lat 30-40, lon -75 to -60) and converts the raw u/v current
components into a scalar speed (knots) and "flowing toward" compass
direction (0-360deg), matching the current_speed/current_dir inputs the
Loop 6 isochrone solver already expects.
"""
import math
import os
from datetime import datetime, timezone

import xarray as xr

# NOAA serves RTOFS via NOMADS OPeNDAP; the exact catalog path and variable
# names have drifted across RTOFS releases and we can't verify connectivity
# from this sandbox, so treat this as best-effort. Any failure (network,
# schema change, auth) falls through to the mocked Gulf Stream grid below
# rather than crashing the pipeline - confirm this path against NOMADS'
# current catalog before relying on it operationally.
RTOFS_OPENDAP_TEMPLATE = (
    "https://nomads.ncep.noaa.gov/dods/rtofs/rtofs_global{date:%Y%m%d}/"
    "rtofs_glo_2ds_forecast_3hrly_diag"
)

BOUNDING_BOX = {"lat_min": 30.0, "lat_max": 40.0, "lon_min": -75.0, "lon_max": -60.0}


class CurrentIngestionEngine:
    def __init__(self, storage_dir="data"):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        self.dataset = None
        self.latest_file = os.path.join(self.storage_dir, "live_currents.nc")

    def fetch_rtofs_slice(self):
        """Downloads a real-time ocean current grid subset from NOAA/RTOFS
        via OPeNDAP and caches it to disk as NetCDF."""
        print("🌊 Starlink Interface Active: Fetching RTOFS Gulf Stream vector data...")
        url = RTOFS_OPENDAP_TEMPLATE.format(date=datetime.now(timezone.utc))

        try:
            remote = xr.open_dataset(url)
            lat_name = "lat" if "lat" in remote.coords else "latitude"
            lon_name = "lon" if "lon" in remote.coords else "longitude"

            lon_min, lon_max = BOUNDING_BOX["lon_min"], BOUNDING_BOX["lon_max"]
            if float(remote[lon_name].max()) > 180:
                lon_min, lon_max = lon_min % 360, lon_max % 360

            subset = remote.sel({
                lat_name: slice(BOUNDING_BOX["lat_min"], BOUNDING_BOX["lat_max"]),
                lon_name: slice(lon_min, lon_max),
            })[["u", "v"]].load()

            subset.to_netcdf(self.latest_file)
            print(f"✅ Ocean model download successful: Saved to {self.latest_file}")
            return True
        except Exception as e:
            print(f"❌ Oceanographic data download failed: {e}")
            return False

    def load_dataset(self):
        """Loads the cached NetCDF ocean current grid into memory."""
        if os.path.exists(self.latest_file):
            self.dataset = xr.open_dataset(self.latest_file)
            print("🌊 Gulf Stream velocity matrices loaded into local memory matrix.")
        else:
            # Fallback mock dataset generation for desktop loop development/testing
            print("⚠️ No live NetCDF file found. Injecting a simulated Gulf Stream core vector grid...")
            self.dataset = "mocked"

    def get_current_vector(self, lat, lon):
        """
        Converts Eastward (u) and Northward (v) ocean velocities into Speed & Direction.
        Outputs speed in Knots and Direction in Compass Degrees (the direction
        the current is flowing TOWARD, matching Loop 6's current_dir input).
        """
        if isinstance(self.dataset, str) and self.dataset == "mocked":
            # If our mock is in the core Gulf Stream area, return a realistic heavy current push
            if 34.0 <= lat <= 36.0 and -73.0 <= lon <= -70.0:
                return 4.2, 55.0  # 4.2 knots surging North-East
            return 0.4, 180.0  # Standard weak open ocean drift elsewhere

        try:
            lat_name = "lat" if "lat" in self.dataset.coords else "latitude"
            lon_name = "lon" if "lon" in self.dataset.coords else "longitude"

            # Ocean model distributions vary between -180/180 and 0-360 East
            # longitude, so normalize the query to whichever this dataset
            # actually uses rather than assuming one (see Loop 7's GFS fix
            # for the same class of bug).
            lon_coord = self.dataset[lon_name]
            query_lon = lon % 360 if float(lon_coord.max()) > 180 else lon

            point_data = self.dataset.sel(**{lat_name: lat, lon_name: query_lon}, method="nearest")
            u_current = float(point_data["u"].values)  # Eastward speed vector in m/s
            v_current = float(point_data["v"].values)  # Northward speed vector in m/s

            # Math conversion: m/s to Knots (1 m/s = 1.94384 knots)
            current_speed = math.sqrt(u_current**2 + v_current**2) * 1.94384

            # Math conversion: Vectors to direction the current is flowing TOWARD
            current_dir = (math.degrees(math.atan2(u_current, v_current)) + 360) % 360

            return round(current_speed, 2), round(current_dir, 0)
        except Exception as e:
            print(f"⚠️ Current lookup failed ({e}), defaulting to dead calm water.")
            return 0.0, 0.0  # Default to dead calm water if parsing fails


if __name__ == "__main__":
    engine = CurrentIngestionEngine()

    print("Running Loop 8 Validation: Downloading and parsing live ocean current data...")
    engine.fetch_rtofs_slice()
    engine.load_dataset()

    # Same forecast nodes GribWarperEngine (Loop 4) tracks ahead of the boat,
    # plus a point clear of the Gulf Stream core for contrast.
    sample_points = [(35.0, -70.0), (35.5, -69.5), (36.0, -69.0), (38.0, -65.0)]
    print("\nCurrent vectors at sample nodes:")
    for lat, lon in sample_points:
        speed, direction = engine.get_current_vector(lat, lon)
        print(f"  Node ({lat}, {lon}) -> {speed}kt @ {direction} deg")
