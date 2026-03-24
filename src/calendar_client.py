"""
macOS EventKit calendar client.

Reads events from any calendar synced to macOS Calendar (including Google
Calendar, iCloud, Exchange, etc.). No GCP setup or OAuth credentials needed —
macOS handles access via a standard system permission dialog.

Prerequisite: add your Google account to macOS under
  System Settings → Internet Accounts → Google → enable Calendars
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

import EventKit
from Foundation import NSDate


def _datetime_to_nsdate(dt: datetime) -> NSDate:
    return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())


class CalendarClient:
    def __init__(self) -> None:
        self._store = EventKit.EKEventStore.alloc().init()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def is_authorized(self) -> bool:
        status = EventKit.EKEventStore.authorizationStatusForEntityType_(
            EventKit.EKEntityTypeEvent
        )
        # EKAuthorizationStatusAuthorized / EKAuthorizationStatusFullAccess = 3
        return int(status) == 3

    def authorize(self) -> bool:
        """
        Request calendar access via the native macOS permission dialog.
        Blocking — call from a background thread.
        Returns True if access was granted.
        """
        done = threading.Event()
        result = [False]

        def _callback(granted: bool, error: Any) -> None:
            result[0] = bool(granted)
            done.set()

        # macOS 14+ prefers requestFullAccessToEventsWithCompletion_
        if hasattr(self._store, "requestFullAccessToEventsWithCompletion_"):
            self._store.requestFullAccessToEventsWithCompletion_(_callback)
        else:
            self._store.requestAccessToEntityType_completion_(
                EventKit.EKEntityTypeEvent, _callback
            )

        done.wait(timeout=60)
        return result[0]

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def get_todays_events(self) -> list[dict[str, Any]]:
        """
        Return timed events from now until end of today across all calendars.
        Each item: {"id": str, "summary": str, "start_dt": datetime (UTC-aware)}
        All-day events are skipped.
        """
        if not self.is_authorized():
            return []

        now = datetime.now(timezone.utc)
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)

        predicate = self._store.predicateForEventsWithStartDate_endDate_calendars_(
            _datetime_to_nsdate(now),
            _datetime_to_nsdate(end_of_day),
            None,  # None = all calendars
        )
        ek_events = self._store.eventsMatchingPredicate_(predicate) or []

        events: list[dict[str, Any]] = []
        for ek_event in ek_events:
            if ek_event.isAllDay():
                continue

            ts = ek_event.startDate().timeIntervalSince1970()
            start_dt = datetime.fromtimestamp(ts, tz=timezone.utc)

            events.append(
                {
                    "id": str(ek_event.eventIdentifier()),
                    "summary": str(ek_event.title() or "(No title)"),
                    "start_dt": start_dt,
                }
            )

        events.sort(key=lambda e: e["start_dt"])
        return events
