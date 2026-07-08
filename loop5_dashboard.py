from flask import Flask, render_template_string, jsonify
import threading
import time

# Import your custom modules from the previous steps
from loop1_replay import LogPlaybackSystem
from loop2_analyzer import SecondStormCompleteMatrix
from loop6_router import IsochroneSolver

app = Flask(__name__)

# Initialize our core background engines
log_stream = LogPlaybackSystem()
matrix_engine = SecondStormCompleteMatrix()
router = IsochroneSolver()

ROUTE_INTERVAL_SECONDS = 900.0  # re-solve the route every 15 minutes

# The telemetry replay has no live GPS feed, so anchor route projections at
# the same reference position loop4/loop6 use for their own validation runs.
BOAT_LAT, BOAT_LON = 35.0, -70.0

# Global thread-safe state variable
current_boat_state = {}

def telemetry_worker():
    """Background thread running continuously on the Pi to process data."""
    global current_boat_state
    next_route_at = 0.0  # solve a route on the very first tick
    route_track = []
    route_updated_at = None

    while True:
        # 1. Pull the next packet from our playback file (Loop 1)
        telemetry = log_stream.pull_live_packet()

        # 2. Process metrics through Second Storm's polar chart (Loop 2)
        target_btv, efficiency = matrix_engine.evaluate_performance(
            telemetry["twa"], telemetry["tws"], telemetry["stw"]
        )

        # 3. Every 15 minutes, re-run the full isochrone route projection
        # (Loop 6) so the front-end map's track line stays current.
        now = time.time()
        if now >= next_route_at:
            true_wind_dir = (telemetry["cog"] - telemetry["twa"]) % 360
            route_track = router.solve_route(
                BOAT_LAT, BOAT_LON, tws=telemetry["tws"], twd=true_wind_dir
            )
            route_updated_at = time.strftime("%H:%M:%S")
            next_route_at = now + ROUTE_INTERVAL_SECONDS

        # 4. Pack everything into our global state
        current_boat_state = {
            "time": time.strftime("%H:%M:%S"),
            "twa": telemetry["twa"],
            "tws": telemetry["tws"],
            "stw": telemetry["stw"],
            "sog": telemetry["sog"],
            "cog": telemetry["cog"],
            "target_btv": target_btv,
            "efficiency": efficiency,
            "route_track": route_track,
            "route_updated_at": route_updated_at,
        }
        time.sleep(1.0) # Updates once per second

# --- WEB SERVER ENDPOINTS ---

@app.route('/')
def index():
    """Serves the main dashboard page layout directly from a string template."""
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Second Storm Tactical Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: -apple-system, sans-serif; background: #121214; color: #e1e1e6; margin: 0; padding: 20px; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; }
            .card { background: #1a1a1e; border-radius: 12px; padding: 20px; text-align: center; border: 1px solid #29292e; }
            .large-text { font-size: 3rem; font-weight: bold; margin: 10px 0; color: #fff; }
            .unit { font-size: 1rem; color: #a1a1aa; }
            .alert-box { background: #231515; border: 1px solid #c53030; color: #fc8181; border-radius: 8px; padding: 15px; margin-bottom: 20px; font-weight: bold; display: none;}
            h1 { font-size: 1.8rem; margin-bottom: 5px; }
            p { margin-top: 0; color: #a1a1aa; }
        </style>
        <script>
            async function updateDashboard() {
                const response = await fetch('/api/telemetry');
                const data = await response.json();
                if (!('stw' in data)) return;

                // Update raw metrics
                document.getElementById('stw').innerText = data.stw.toFixed(2);
                document.getElementById('target_btv').innerText = data.target_btv.toFixed(2);
                document.getElementById('efficiency').innerText = data.efficiency.toFixed(1) + '%';
                document.getElementById('tws').innerText = data.tws.toFixed(1);
                document.getElementById('twa').innerText = data.twa.toFixed(0) + '°';

                // Color-code efficiency performance thresholds
                const effCard = document.getElementById('eff-card');
                if (data.efficiency >= 98) effCard.style.borderColor = '#22c55e';
                else if (data.efficiency >= 90) effCard.style.borderColor = '#eab308';
                else effCard.style.borderColor = '#ef4444';

                // Manage Dynamic Alert Status Flags
                const alert = document.getElementById('trim-alert');
                if (data.efficiency < 92) {
                    alert.style.display = 'block';
                    alert.innerText = `⚠️ PERFORMANCE ALERT: Target is ${data.target_btv.toFixed(2)} kts, sailing at ${data.stw.toFixed(2)} kts. Check trim or sail selection.`;
                } else {
                    alert.style.display = 'none';
                }
            }
            setInterval(updateDashboard, 1000); // Poll every second
        </script>
    </head>
    <body>
        <h1>SECOND STORM</h1>
        <p>ORC Tactical Telemetry Engine (USA 61825)</p>

        <div id="trim-alert" class="alert-box"></div>

        <div class="grid">
            <div class="card"><h3>Boat Speed (STW)</h3><div class="large-text" id="stw">0.00</div><span class="unit">knots</span></div>
            <div class="card"><h3>ORC Target (BTV)</h3><div class="large-text" id="target_btv">0.00</div><span class="unit">knots</span></div>
            <div id="eff-card" class="card" style="border-width: 2px;"><h3>Polar Efficiency</h3><div class="large-text" id="efficiency">0.0%</div><span class="unit">target yield</span></div>
            <div class="card"><h3>True Wind</h3><div class="large-text"><span id="tws">0.0</span><span style="font-size:1.5rem;color:#a1a1aa;">k</span> / <span id="twa">0°</span></div><span class="unit">speed / angle</span></div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html_template)

@app.route('/api/telemetry')
def get_telemetry():
    """Exposes a clean JSON endpoint for asynchronous Javascript polling."""
    return jsonify(current_boat_state)


if __name__ == "__main__":
    worker_thread = threading.Thread(target=telemetry_worker, daemon=True)
    worker_thread.start()
    app.run(host="0.0.0.0", port=5000, debug=False)
