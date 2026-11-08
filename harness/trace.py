"""Append-only event stream; API keys and authorization headers never enter it."""
import json
import time
from pathlib import Path


class Trace:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.start = time.monotonic()
        self.events = []

    def emit(self, kind: str, **data):
        event = {"event": kind, "elapsed_s": round(time.monotonic() - self.start, 6), **data}
        self.events.append(event)
        with self.path.open("a") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event
