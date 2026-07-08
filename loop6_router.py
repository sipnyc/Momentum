"""Loop 6: Isochrone Weather Router

Projects a fan of candidate headings forward in 15-minute steps, scoring
each node against Second Storm's full ORC deck-state matrix (Loop 2) and
folding in ocean current drift via vector addition.
"""
import math

from loop2_analyzer import SecondStormCompleteMatrix

DELTA_T_SECONDS = 900.0  # 15-minute isochrone time step


class IsochroneSolver:
    def __init__(self, destination_lat=32.3, destination_lon=-64.8):
        self.matrix = SecondStormCompleteMatrix()
        self.dest_lat = destination_lat
        self.dest_lon = destination_lon

    def project_isochrone_node(self, start_lat, start_lon, heading, tws, twd, current_speed, current_dir):
        """Calculates a single forward node step factoring in polars, current, and wave penalties."""
        twa = (heading - twd) % 360

        # 1. Fetch performance profile from Second Storm's polar spline
        deck_state = self.matrix.analyze_deck_state(twa, tws, stw=0.0)
        stw_target = deck_state["target_btv"]

        # 2. Apply Wind-Over-Current Wave Penalty Logic
        # If heavy air and heading directly into an opposing ocean current vector
        if tws > 25.0 and abs((twd - current_dir) % 360) > 135:
            stw_target *= 0.85  # 15% structural speed penalty for square wave resistance

        # 3. Calculate Boat Speed Vector Components (Nautical Miles per Hour)
        boat_vx = stw_target * math.sin(math.radians(heading))
        boat_vy = stw_target * math.cos(math.radians(heading))

        # 4. Calculate Ocean Current Vector Components
        current_vx = current_speed * math.sin(math.radians(current_dir))
        current_vy = current_speed * math.cos(math.radians(current_dir))

        # 5. Vector Addition: Resulting Speed Over Ground (SOG) vector
        sog_vx = boat_vx + current_vx
        sog_vy = boat_vy + current_vy

        # Advance position by 15 minutes (0.25 hours)
        delta_time = DELTA_T_SECONDS / 3600.0
        delta_lat = (sog_vy * delta_time) / 60.0
        delta_lon = (sog_vx * delta_time) / (60.0 * math.cos(math.radians(start_lat)))

        return start_lat + delta_lat, start_lon + delta_lon

    def project_isochrone_fan(self, start_lat, start_lon, tws, twd, current_speed, current_dir,
                               heading_step=15.0):
        """Projects one time step of nodes across a fan of candidate headings (0-359 deg)."""
        fan = {}
        heading = 0.0
        while heading < 360.0:
            fan[heading] = self.project_isochrone_node(
                start_lat, start_lon, heading, tws, twd, current_speed, current_dir
            )
            heading += heading_step
        return fan

    def _distance_nm(self, lat1, lon1, lat2, lon2):
        lat_dist = (lat2 - lat1) * 60.0
        lon_dist = (lon2 - lon1) * 60.0 * math.cos(math.radians(lat1))
        return math.hypot(lat_dist, lon_dist)

    def solve_route(self, start_lat, start_lon, tws, twd, current_speed=0.0, current_dir=0.0,
                     heading_step=15.0, max_steps=48, arrival_radius_nm=5.0):
        """Chains isochrone fan steps into a full route toward the destination.

        At each 15-minute step, projects the full heading fan and greedily
        advances along whichever candidate node lands closest to the
        destination (a standard simplification of isochrone routing: chase
        the frontier point with the best progress toward the mark rather
        than expanding every branch of the tree). Stops once within
        `arrival_radius_nm` of the destination or after `max_steps` steps
        (48 steps * 15 min = 12 hours of projected track).
        """
        lat, lon = start_lat, start_lon
        route_track = [(lat, lon)]

        for _ in range(max_steps):
            if self._distance_nm(lat, lon, self.dest_lat, self.dest_lon) <= arrival_radius_nm:
                break
            fan = self.project_isochrone_fan(lat, lon, tws, twd, current_speed, current_dir, heading_step)
            lat, lon = min(
                fan.values(),
                key=lambda node: self._distance_nm(node[0], node[1], self.dest_lat, self.dest_lon)
            )
            route_track.append((lat, lon))

        return route_track


if __name__ == "__main__":
    solver = IsochroneSolver()

    print("Running Loop 6 Validation: Projecting isochrone heading fan...")
    boat_lat, boat_lon = 35.0, -70.0

    # Moderate breeze, benign current
    fan = solver.project_isochrone_fan(
        boat_lat, boat_lon, tws=14.0, twd=90.0, current_speed=1.5, current_dir=270.0, heading_step=45.0
    )
    print("\nModerate breeze (TWS 14kt), following current:")
    for heading, (lat, lon) in fan.items():
        print(f"  Heading {heading:>5.1f} deg -> node ({lat:.4f}, {lon:.4f})")

    # Heavy air with wind-against-current square waves (TWS 28kt, wind vs current > 135 deg apart)
    lat, lon = solver.project_isochrone_node(
        boat_lat, boat_lon, heading=90.0, tws=28.0, twd=90.0, current_speed=2.0, current_dir=270.0
    )
    print(f"\nHeavy air (TWS 28kt) wind-against-current node -> ({lat:.4f}, {lon:.4f})")

    route = solver.solve_route(boat_lat, boat_lon, tws=14.0, twd=90.0, current_speed=1.0, current_dir=250.0)
    print(f"\nFull route projection toward destination ({solver.dest_lat}, {solver.dest_lon}):")
    print(f"  {len(route)} waypoints, start {route[0]} -> end {route[-1]}")
