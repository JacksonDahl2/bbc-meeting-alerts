"""
Background scheduler thread: polls calendar, fires the BBC jingle alert,
and persists deduplication state.

Alerted: ~/.bbc-alert/alerted.json  {"<event_id>": "<ISO timestamp of alert>"}
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable

from calendar_client import CalendarClient

PREFS_DIR = Path.home() / ".bbc-alert"
ALERTED_PATH = PREFS_DIR / "alerted.json"

ALERT_SECONDS = 15  # play jingle this many seconds before meeting
POLL_INTERVAL = 60  # seconds between calendar polls
ALERTED_TTL_HOURS = 24  # purge alerted entries after this many hours


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _save_json(path: Path, data: Any) -> None:
    PREFS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


class Scheduler(threading.Thread):
    def __init__(
        self,
        client: CalendarClient,
        audio_path: str,
        on_events_updated: Callable[[list[dict]], None] | None = None,
    ) -> None:
        super().__init__(daemon=True, name="BBCAlertScheduler")
        self._client = client
        self._audio_path = audio_path
        self._on_events_updated = on_events_updated

        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self._events: list[dict] = []
        self._alerted_ids: set[str] = set(self._load_alerted().keys())
        self._audio_proc: subprocess.Popen | None = None

    # ------------------------------------------------------------------
    # Public API (thread-safe)
    # ------------------------------------------------------------------

    def get_events(self) -> list[dict]:
        with self._lock:
            return list(self._events)

    def stop(self) -> None:
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Thread main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as exc:
                print(f"[Scheduler] Error during tick: {exc}")
            self._stop_event.wait(timeout=POLL_INTERVAL)

    def _tick(self) -> None:
        events = self._client.get_todays_events()

        with self._lock:
            self._events = events

        if self._on_events_updated:
            self._on_events_updated(events)

        now = datetime.now(timezone.utc)
        self._purge_old_alerted()

        for event in events:
            self._check_alert(event, now)

    def _check_alert(self, event: dict, now: datetime) -> None:
        event_id = event["id"]
        if event_id in self._alerted_ids:
            return
        delta = (event["start_dt"] - now).total_seconds()
        if 0 <= delta <= ALERT_SECONDS:
            self._fire_alert(event_id)

    def _fire_alert(self, event_id: str) -> None:
        self._alerted_ids.add(event_id)
        self._persist_alerted(event_id)
        self._play_audio()

    def _play_audio(self) -> None:
        if not os.path.exists(self._audio_path):
            print(f"[Scheduler] Audio file not found: {self._audio_path}")
            return
        self.stop_audio()
        with self._lock:
            self._audio_proc = subprocess.Popen(
                ["afplay", self._audio_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def stop_audio(self) -> None:
        with self._lock:
            proc = self._audio_proc
            self._audio_proc = None
        if proc and proc.poll() is None:
            proc.terminate()

    def play_test_alert(self) -> None:
        self._play_audio()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load_alerted(self) -> dict[str, str]:
        return _load_json(ALERTED_PATH, {})

    def _persist_alerted(self, event_id: str) -> None:
        data = self._load_alerted()
        data[event_id] = datetime.now(timezone.utc).isoformat()
        _save_json(ALERTED_PATH, data)

    def _purge_old_alerted(self) -> None:
        data = self._load_alerted()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ALERTED_TTL_HOURS)
        cleaned = {
            eid: ts for eid, ts in data.items() if datetime.fromisoformat(ts) > cutoff
        }
        if len(cleaned) != len(data):
            _save_json(ALERTED_PATH, cleaned)
            self._alerted_ids = set(cleaned.keys())
