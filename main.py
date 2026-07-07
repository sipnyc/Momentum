"""Momentum Navigation Core: unified entry point.

Syncs GRIB/current forecast data before the dashboard's engines
initialize, then launches the background telemetry loop and the web
cockpit together.
"""
import threading

from loop7_grib_downloader import GribIngestionEngine
from loop8_currents import CurrentIngestionEngine


def initial_data_sync():
    """Fires over the Starlink ethernet interface on startup to prep our routing grids."""
    print("🚀 INITIALIZING MOMENTUM NAVIGATION CORE...")

    grib = GribIngestionEngine()
    currents = CurrentIngestionEngine()

    # Run pre-departure downloads
    grib.download_gfs_slice()
    grib.load_dataset()

    currents.fetch_rtofs_slice()
    currents.load_dataset()
    print("📊 Core matrices primed and ready for tactical loops.")


if __name__ == "__main__":
    # 1. Run our initial satellite weather sync. This has to happen before
    # loop5_dashboard is imported below: importing it constructs
    # SecondStormMatrix/IsochroneSolver (and IsochroneSolver's own
    # CurrentIngestionEngine) immediately at module load time, so importing
    # any earlier would make this sync run too late to matter - it would
    # just be a second, redundant download after those engines already
    # loaded on their own.
    initial_data_sync()

    from loop5_dashboard import app, telemetry_worker

    # 2. Spin up the background telemetry processor thread
    t = threading.Thread(target=telemetry_worker, daemon=True)
    t.start()

    # 3. Launch the unified cockpit web interface
    print("📡 Web Server Broadcasting. Connect devices via boat Wi-Fi on Port 5000.")
    app.run(host="0.0.0.0", port=5000, debug=False)
