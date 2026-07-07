"""Loop 1: Data Ingestion & Parser Replay

Parses Second Storm's historical downloaded data logs and replays them to
simulate a live NMEA network buffer for desktop debugging.
"""
import csv
import json
import time
from pathlib import Path

DEFAULT_LOG_PATH = Path(__file__).parent / "data" / "second_storm_log.jsonl"

# Maps raw log field names to the canonical NMEA buffer keys. Extend this
# if your data logger uses different field names than the ones below.
KEY_MAP = {
    "twa": "twa", "true_wind_angle": "twa",
    "tws": "tws", "true_wind_speed": "tws",
    "stw": "stw", "speed_through_water": "stw",
    "sog": "sog", "speed_over_ground": "sog",
    "cog": "cog", "course_over_ground": "cog",
}

REQUIRED_FIELDS = ("twa", "tws", "stw", "sog", "cog")

# Used only if no log file can be found or parsed on disk.
FALLBACK_ROWS = [
    {"twa": 60.0, "tws": 12.0, "stw": 6.99, "sog": 7.10, "cog": 115.0},
    {"twa": 70.0, "tws": 14.0, "stw": 7.73, "sog": 7.90, "cog": 122.0},
    {"twa": 110.0, "tws": 16.0, "stw": 8.76, "sog": 9.10, "cog": 145.0},
    {"twa": 135.0, "tws": 20.0, "stw": 8.82, "sog": 9.40, "cog": 160.0},
]


def _normalize_row(raw):
    row = {}
    for key, value in raw.items():
        canonical = KEY_MAP.get(str(key).strip().lower())
        if canonical:
            row[canonical] = float(value)
    missing = [field for field in REQUIRED_FIELDS if field not in row]
    if missing:
        raise ValueError(f"Log row missing fields {missing}: {raw}")
    return row


def _load_jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(_normalize_row(json.loads(line)))
    return rows


def _load_json(path):
    with open(path) as f:
        data = json.load(f)
    return [_normalize_row(row) for row in data]


def _load_csv(path):
    with open(path, newline="") as f:
        return [_normalize_row(row) for row in csv.DictReader(f)]


LOADERS = {".jsonl": _load_jsonl, ".json": _load_json, ".csv": _load_csv}


def load_log(path):
    path = Path(path)
    loader = LOADERS.get(path.suffix.lower())
    if loader is None:
        raise ValueError(f"Unsupported log format: {path.suffix}")
    return loader(path)


class LogPlaybackSystem:
    """Streams parsed historical log rows to simulate a live NMEA network buffer."""

    def __init__(self, log_path=DEFAULT_LOG_PATH):
        try:
            self.playback_queue = load_log(log_path)
            if not self.playback_queue:
                raise ValueError("log file is empty")
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            self.playback_queue = FALLBACK_ROWS
        self.pointer = 0

    def pull_live_packet(self):
        if self.pointer >= len(self.playback_queue):
            self.pointer = 0  # Infinite loop for desktop debugging
        packet = self.playback_queue[self.pointer]
        self.pointer += 1
        return packet

    def stream(self, interval=1.0, count=None):
        """Yield packets `interval` seconds apart, like a live NMEA feed."""
        sent = 0
        while count is None or sent < count:
            yield self.pull_live_packet()
            sent += 1
            time.sleep(interval)


if __name__ == "__main__":
    tracker = LogPlaybackSystem()
    print("Running Loop 1 Validation: Reading static log rows...")
    for i in range(4):
        print(f"Row {i}: {json.dumps(tracker.pull_live_packet())}")
