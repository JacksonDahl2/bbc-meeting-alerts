"""
BBC Alert — macOS menubar app.

Plays the BBC News jingle 15 seconds before calendar meetings, then shows
a live countdown in the menubar with red flashing as the meeting approaches.

Run in development:
    uv run python src/app.py

Build as .app bundle:
    uv run python setup.py py2app        # full build
    uv run python setup.py py2app -A     # alias build (faster, dev only)
"""

from __future__ import annotations

import os
import plistlib
import subprocess
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

import rumps
from Quartz import CGColorCreateSRGB

_RED_CGCOLOR = CGColorCreateSRGB(1.0, 0.23, 0.19, 1.0)  # system red

from calendar_client import CalendarClient  # noqa: E402 (same dir when run via src/)
from scheduler import Scheduler

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def _resource_path(filename: str) -> str:
    # In a bundled .app, RESOURCEPATH points to the bundle's Resources dir.
    # In dev, app.py lives in src/ and assets live one level up at the project root.
    if "RESOURCEPATH" in os.environ:
        return os.path.join(os.environ["RESOURCEPATH"], filename)
    src_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(src_dir), filename)


AUDIO_PATH = _resource_path("assets/bbc_news.mp3")

LAUNCH_AGENT_PLIST = Path.home() / "Library" / "LaunchAgents" / "com.bbc-alert.plist"
APP_BUNDLE_PATH = "/Applications/BBC Alert.app/Contents/MacOS/BBC Alert"

# ---------------------------------------------------------------------------
# Countdown constants
# ---------------------------------------------------------------------------

_COUNTDOWN_SECONDS = 15  # when to start showing the countdown
_LIVE_DISPLAY_SECONDS = 4  # how long to show "is live!" after meeting starts

# ---------------------------------------------------------------------------
# LaunchAgent helpers
# ---------------------------------------------------------------------------


def _is_launch_at_login_enabled() -> bool:
    return LAUNCH_AGENT_PLIST.exists()


def _write_launch_agent_plist() -> None:
    plist_data = {
        "Label": "com.bbc-alert",
        "ProgramArguments": [APP_BUNDLE_PATH],
        "RunAtLoad": True,
        "KeepAlive": False,
    }
    LAUNCH_AGENT_PLIST.parent.mkdir(parents=True, exist_ok=True)
    with open(LAUNCH_AGENT_PLIST, "wb") as f:
        plistlib.dump(plist_data, f)
    subprocess.run(["launchctl", "load", str(LAUNCH_AGENT_PLIST)], capture_output=True)


def _remove_launch_agent_plist() -> None:
    if LAUNCH_AGENT_PLIST.exists():
        subprocess.run(
            ["launchctl", "unload", str(LAUNCH_AGENT_PLIST)], capture_output=True
        )
        LAUNCH_AGENT_PLIST.unlink()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


class BBCAlertApp(rumps.App):
    def __init__(self) -> None:
        icon_path = _resource_path("assets/icon.svg")
        super().__init__(
            "BBC Alert",
            title=None,
            icon=icon_path if os.path.exists(icon_path) else None,
            template=True,
            quit_button=None,
        )

        self._client = CalendarClient()
        self._scheduler = Scheduler(self._client, AUDIO_PATH)

        # Auth state
        self._auth_in_progress = False
        self._auth_just_completed = False

        # Countdown state
        self._counting_down = False
        self._flash_tick = 0
        self._live_event: dict | None = None
        self._live_shown_at: datetime | None = None
        self._test_event: dict | None = None

        # Menu items
        self._meeting_items: list[rumps.MenuItem] = []
        self._test_item = rumps.MenuItem("Test alert", callback=self._on_test_alert)
        self._silence_item = rumps.MenuItem("Silence", callback=self._on_silence)
        self._login_item = rumps.MenuItem(
            (
                "✅ Launch at login"
                if _is_launch_at_login_enabled()
                else "Launch at login"
            ),
            callback=self._on_toggle_launch_at_login,
        )
        self._auth_item = self._make_auth_item()
        self._quit_item = rumps.MenuItem("Quit", callback=rumps.quit_application)

        self._rebuild_menu()
        self._scheduler.start()

    # ------------------------------------------------------------------
    # Menu construction
    # ------------------------------------------------------------------

    def _make_auth_item(self) -> rumps.MenuItem:
        if self._client.is_authorized():
            return rumps.MenuItem("✅ Calendar access granted")
        return rumps.MenuItem("Grant Calendar Access", callback=self._on_authorize)

    def _rebuild_menu(self) -> None:
        items: list = []
        if self._meeting_items:
            items.extend(self._meeting_items)
        else:
            items.append(rumps.MenuItem("No upcoming meetings today"))
        items.append(rumps.separator)
        items.append(self._test_item)
        items.append(self._silence_item)
        items.append(self._login_item)
        items.append(rumps.separator)
        items.append(self._auth_item)
        items.append(self._quit_item)
        self.menu.clear()
        self.menu = items

    # ------------------------------------------------------------------
    # Icon + menubar title helpers
    # ------------------------------------------------------------------

    def _set_menubar_title(self, text: str, red: bool = False) -> None:
        self.title = text
        button = self._nsapp.nsstatusitem.button()
        button.setWantsLayer_(True)
        layer = button.layer()
        layer.setBackgroundColor_(_RED_CGCOLOR if red else None)
        layer.setCornerRadius_(4.0 if red else 0.0)

    def _reset_menubar_title(self) -> None:
        # Setting title=None makes rumps show the icon instead of text
        self.title = None
        button = self._nsapp.nsstatusitem.button()
        button.setWantsLayer_(True)
        button.layer().setBackgroundColor_(None)
        button.layer().setCornerRadius_(0.0)

    # ------------------------------------------------------------------
    # Timers
    # ------------------------------------------------------------------

    @rumps.timer(60)
    def _refresh_timer(self, _sender: rumps.Timer) -> None:
        self._refresh_meetings()
        self._refresh_auth_item()

    @rumps.timer(5)
    def _auth_poll_timer(self, _sender: rumps.Timer) -> None:
        if self._auth_just_completed:
            self._auth_just_completed = False
            self._auth_in_progress = False
            self._refresh_auth_item()
            self._refresh_meetings()

    @rumps.timer(0.25)
    def _countdown_timer(self, _sender: rumps.Timer) -> None:
        now = datetime.now(timezone.utc)

        # If we're in the "is live!" display window, hold until it expires
        if self._live_event is not None:
            elapsed = (now - self._live_shown_at).total_seconds()
            if elapsed < _LIVE_DISPLAY_SECONDS:
                return
            # Live display done — reset
            self._live_event = None
            self._live_shown_at = None
            self._counting_down = False
            self._flash_tick = 0
            self._test_event = None
            self._reset_menubar_title()
            return

        # Test event takes priority over real events
        if self._test_event is not None:
            next_event = self._test_event
        else:
            events = self._scheduler.get_events()
            next_event = events[0] if events else None

        if next_event is None:
            if self._counting_down:
                self._counting_down = False
                self._flash_tick = 0
                self._reset_menubar_title()
            return

        delta = (next_event["start_dt"] - now).total_seconds()
        name = next_event["summary"]

        if delta > _COUNTDOWN_SECONDS:
            # Not yet time — ensure we're reset
            if self._counting_down:
                self._counting_down = False
                self._flash_tick = 0
                self._reset_menubar_title()
            return

        if delta <= 0:
            # Meeting has started — only trigger live display if we were counting down
            if self._counting_down:
                self._counting_down = False
                self._flash_tick = 0
                self._live_event = next_event
                self._live_shown_at = now
                self._set_menubar_title(f"<{name}> is live!")
            return

        # Active countdown: 0 < delta <= 15
        self._counting_down = True
        self._flash_tick += 1
        seconds = int(delta) + 1  # round up so we show "1s" not "0s"
        text = f"<{name}> in {seconds}s"

        if seconds <= 5:
            # Flash background twice per second: toggle every 0.25s tick
            self._set_menubar_title(text, red=self._flash_tick % 2 == 0)
        elif seconds <= 10:
            # Flash background once per second: toggle every 2 ticks (0.5s on, 0.5s off)
            self._set_menubar_title(text, red=(self._flash_tick // 2) % 2 == 0)
        else:
            # 11-15s: plain text, no flash
            self._set_menubar_title(text)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_authorize(self, _sender: rumps.MenuItem) -> None:
        if self._auth_in_progress:
            return
        self._auth_in_progress = True
        self._auth_item.title = "Requesting access…"

        def _auth_thread() -> None:
            try:
                granted = self._client.authorize()
                if granted:
                    self._auth_just_completed = True
                else:
                    rumps.alert(
                        title="Calendar access denied",
                        message=(
                            "BBC Alert was not granted calendar access.\n\n"
                            "To fix this: System Settings → Privacy & Security → "
                            "Calendars → enable BBC Alert (or Terminal in dev mode)."
                        ),
                    )
                    self._auth_in_progress = False
            except Exception as exc:
                rumps.alert(title="Calendar access failed", message=str(exc))
                self._auth_in_progress = False

        threading.Thread(target=_auth_thread, daemon=True).start()

    def _on_test_alert(self, _sender: rumps.MenuItem) -> None:
        if not os.path.exists(AUDIO_PATH):
            rumps.alert(
                title="Audio file missing",
                message=(
                    f"BBC News jingle not found at:\n{AUDIO_PATH}\n\n"
                    "Run setup first:\n    uv run python download_audio.py"
                ),
            )
            return
        # Play audio now (mirrors when it fires for real — 15s before start)
        self._scheduler.play_test_alert()
        # Inject a fake event starting in 15s so the full countdown plays out
        self._test_event = {
            "id": "__test__",
            "summary": "Test Meeting",
            "start_dt": datetime.now(timezone.utc)
            + timedelta(seconds=_COUNTDOWN_SECONDS),
        }

    def _on_silence(self, _sender: rumps.MenuItem) -> None:
        self._scheduler.stop_audio()

    def _on_toggle_launch_at_login(self, _sender: rumps.MenuItem) -> None:
        if _is_launch_at_login_enabled():
            _remove_launch_agent_plist()
            self._login_item.title = "Launch at login"
        else:
            if not os.path.exists(APP_BUNDLE_PATH):
                rumps.alert(
                    title="App not in /Applications/",
                    message=(
                        "Launch at login requires the app to be installed at:\n"
                        f"{APP_BUNDLE_PATH}\n\n"
                        "Move BBC Alert.app to /Applications/ first."
                    ),
                )
                return
            _write_launch_agent_plist()
            self._login_item.title = "✅ Launch at login"

    # ------------------------------------------------------------------
    # Refresh helpers
    # ------------------------------------------------------------------

    def _refresh_meetings(self) -> None:
        events = self._scheduler.get_events()
        now = datetime.now(timezone.utc)
        items = []
        for event in events:
            start_local = event["start_dt"].astimezone()
            time_str = start_local.strftime("%H:%M")
            summary = event["summary"]
            delta_min = int((event["start_dt"] - now).total_seconds() / 60)
            if delta_min <= 0:
                suffix = " (now)"
            elif delta_min == 1:
                suffix = " (in 1 min)"
            else:
                suffix = f" (in {delta_min} min)"
            items.append(rumps.MenuItem(f"{time_str} — {summary}{suffix}"))
        self._meeting_items = items
        self._rebuild_menu()

    def _refresh_auth_item(self) -> None:
        if self._client.is_authorized():
            self._auth_item.title = "✅ Calendar access granted"
            self._auth_item.set_callback(None)
        else:
            self._auth_item.title = "Grant Calendar Access"
            self._auth_item.set_callback(self._on_authorize)
        self._rebuild_menu()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    BBCAlertApp().run()
