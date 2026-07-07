import itertools


class LogPlaybackSystem:
    """Replays recorded NMEA log packets for downstream performance analysis."""

    def __init__(self):
        self._log = [
            {"timestamp": "12:00:01", "twa": 75.0, "tws": 14.0, "stw": 7.6},
            {"timestamp": "12:00:16", "twa": 110.0, "tws": 16.0, "stw": 8.5},
            {"timestamp": "12:00:31", "twa": 135.0, "tws": 20.0, "stw": 8.9},
            {"timestamp": "12:00:46", "twa": 165.0, "tws": 12.0, "stw": 5.9},
        ]
        self._cycle = itertools.cycle(self._log)

    def pull_live_packet(self):
        return next(self._cycle)
