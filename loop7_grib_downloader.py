"""Loop 7: GFS GRIB Downloader

Fetches a subset of NOAA's GFS wind forecast over HTTP for our bounding box
(lat 30-40, lon -75 to -60), then converts the raw U/V wind grids into True
Wind Speed/Direction nodes shaped for the Loop 4 GRIB warper.
"""
import math
import os
from datetime import datetime, timedelta, timezone

import requests
import xarray as xr

# GFS publishes new cycles every 6 hours but with several hours of processing
# lag, so "now" isn't necessarily available yet. Back off by this much before
# picking the latest synoptic cycle (00/06/12/18Z) to request.
GFS_PUBLISH_LAG_HOURS = 5


class GribIngestionEngine:
    def __init__(self, storage_dir="data"):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        # Set unconditionally (not only on a successful download) so a fresh
        # instance whose own fetch fails still picks up a previously cached
        # forecast from disk instead of falling straight back to defaults.
        self.latest_file = os.path.join(self.storage_dir, "live_forecast.grib2")
        self.dataset = None

    def _latest_gfs_cycle(self):
        """Returns the most recent GFS run that should already be published."""
        now = datetime.now(timezone.utc) - timedelta(hours=GFS_PUBLISH_LAG_HOURS)
        cycle_hour = (now.hour // 6) * 6
        return now.replace(hour=cycle_hour, minute=0, second=0, microsecond=0)

    def download_gfs_slice(self):
        """Fetches a real-time high-resolution wind forecast slice from NOAA via Starlink."""
        print("Starlink Interface Active: Querying NOAA GFS server...")

        gfs_url = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
        cycle = self._latest_gfs_cycle()

        # Bounding box covering the track line to Bermuda
        params = {
            "file": f"gfs.t{cycle:%H}z.pgrb2.0p25.f000",
            "dir": f"/gfs.{cycle:%Y%m%d}/{cycle:%H}/atmos",
            "lev_10_m_above_ground": "on",
            "var_UGRD": "on",
            "var_VGRD": "on",
            "subregion": "",
            "leftlon": "-75", "rightlon": "-60",
            "toplat": "40", "bottomlat": "30",
        }

        try:
            response = requests.get(gfs_url, params=params, timeout=30)
        except requests.RequestException as e:
            print(f"Weather download failed over satellite network: {e}")
            return False

        # NOAA's filter script returns HTTP 200 with an HTML error page for
        # bad/unavailable requests, so a real GRIB2 file (magic bytes "GRIB")
        # is the only reliable success signal.
        if response.status_code == 200 and response.content[:4] == b"GRIB":
            with open(self.latest_file, "wb") as f:
                f.write(response.content)
            print(f"GRIB download successful: Saved to {self.latest_file}")
            return True

        print(f"Weather download failed: HTTP {response.status_code}, "
              f"body starts with {response.content[:80]!r}")
        return False

    def load_dataset(self):
        """Opens the downloaded binary file into memory using xarray."""
        if self.latest_file and os.path.exists(self.latest_file):
            # Engine 'cfgrib' parses the weather metadata variables cleanly
            self.dataset = xr.open_dataset(self.latest_file, engine="cfgrib")
            print("GRIB arrays loaded into local memory matrix.")

    def get_wind_at_node(self, lat, lon):
        """Converts U and V grid vectors into True Wind Speed and True Wind Direction."""
        if self.dataset is None:
            return 15.0, 90.0  # Secure fallback defaults if index is empty

        # GFS grids use 0-360 East longitude, while the rest of this codebase
        # uses negative West longitude (e.g. -70.0). Normalize before lookup
        # so a query like lon=-70.0 doesn't get clamped to the grid's edge.
        gfs_lon = lon % 360

        grid_point = self.dataset.sel(latitude=lat, longitude=gfs_lon, method="nearest")

        u_vector = float(grid_point["u10"].values)  # East-West wind velocity component
        v_vector = float(grid_point["v10"].values)  # North-South wind velocity component

        # Vector components to scalar speed in knots (1 m/s = 1.94384 knots)
        tws_ms = math.sqrt(u_vector**2 + v_vector**2)
        tws_knots = tws_ms * 1.94384

        # Vector components to meteorological "wind FROM" compass degrees
        twd_rad = math.atan2(u_vector, v_vector)
        twd_deg = (math.degrees(twd_rad) + 180) % 360

        return round(tws_knots, 1), round(twd_deg, 0)

    def build_warper_grid(self, coords):
        """Structures wind nodes as {(lat, lon): {"tws": ..., "twd": ...}},
        matching GribWarperEngine.raw_grib_grid in loop4_grib_warper.py so
        this can be dropped straight in as its forecast source."""
        grid = {}
        for lat, lon in coords:
            tws, twd = self.get_wind_at_node(lat, lon)
            grid[(lat, lon)] = {"tws": tws, "twd": twd}
        return grid


if __name__ == "__main__":
    engine = GribIngestionEngine()

    print("Running Loop 7 Validation: Downloading and parsing live GFS wind data...")
    if engine.download_gfs_slice():
        engine.load_dataset()

    # Same forecast nodes GribWarperEngine (Loop 4) tracks ahead of the boat
    track_nodes = [(35.0, -70.0), (35.5, -69.5), (36.0, -69.0), (36.5, -68.5)]
    warper_grid = engine.build_warper_grid(track_nodes)

    print("\nWarper-ready forecast grid:")
    for coords, wind in warper_grid.items():
        print(f"  Node {coords} -> TWS {wind['tws']}kt @ TWD {wind['twd']} deg")
