"""Limits on how many questions /ask accepts, so a public demo can't run up the API bill.

Three limits, checked in this order:
  1. a global cap on questions per day across all visitors,
  2. a per-visitor cap on questions per day,
  3. a per-visitor cap on questions in any rolling 60 seconds.
"Day" means a calendar day in UTC. Counters live in memory, which is fine for a single
running instance; they reset if the app restarts.
"""

import math
import threading
from collections import defaultdict, deque
from datetime import UTC, datetime, time, timedelta

MINUTE = timedelta(minutes=1)


def utc_now():
    return datetime.now(UTC)


def describe_wait(seconds):
    """Turn a number of seconds into friendly text, e.g. '42 seconds' or '5 h 12 min'."""
    if seconds < 120:
        return f"{seconds} seconds"
    hours, minutes = divmod(math.ceil(seconds / 60), 60)
    return f"{hours} h {minutes} min" if hours else f"{minutes} min"


class RateLimitExceeded(Exception):
    """A question was refused. message is shown to the visitor."""

    def __init__(self, message, retry_after_seconds):
        super().__init__(message)
        self.message = message
        self.retry_after_seconds = retry_after_seconds


class QuestionLimiter:
    def __init__(self, per_minute=5, per_day=20, global_daily_cap=100, clock=utc_now):
        self.per_minute = per_minute
        self.per_day = per_day
        self.global_daily_cap = global_daily_cap
        self._clock = clock  # tests pass a fake clock so no real waiting is needed
        # Requests are handled on several threads at once; the lock stops two of them
        # updating the counters at the same moment and both slipping under a limit.
        self._lock = threading.Lock()
        self._day = None
        self._recent = defaultdict(deque)  # visitor -> times of their questions, oldest first
        self._today = defaultdict(int)  # visitor -> questions today
        self._total_today = 0

    def check_and_record(self, visitor):
        """Count one question from visitor, or raise RateLimitExceeded without counting it."""
        with self._lock:
            now = self._clock()
            self._start_new_day_if_needed(now)

            # Forget this visitor's questions that are now more than 60 seconds old.
            recent = self._recent[visitor]
            while recent and now - recent[0] >= MINUTE:
                recent.popleft()

            if self._total_today >= self.global_daily_cap:
                raise RateLimitExceeded(
                    "Daily demo limit reached, please try again tomorrow.",
                    self._seconds_until_tomorrow(now),
                )
            if self._today[visitor] >= self.per_day:
                wait = self._seconds_until_tomorrow(now)
                raise RateLimitExceeded(
                    f"You've reached the limit of {self.per_day} questions per day. "
                    f"Please try again in {describe_wait(wait)}.",
                    wait,
                )
            if len(recent) >= self.per_minute:
                # The oldest of the last few questions is the next one to drop out of the window.
                wait = math.ceil((recent[0] + MINUTE - now).total_seconds())
                raise RateLimitExceeded(
                    f"You've reached the limit of {self.per_minute} questions per minute. "
                    f"Please try again in {describe_wait(wait)}.",
                    wait,
                )

            recent.append(now)
            self._today[visitor] += 1
            self._total_today += 1

    def _start_new_day_if_needed(self, now):
        if now.date() != self._day:
            self._day = now.date()
            self._today.clear()
            self._total_today = 0
            # Drop visitors with no recent questions so memory doesn't grow day after day.
            for visitor in [v for v, times in self._recent.items() if not times]:
                del self._recent[visitor]

    @staticmethod
    def _seconds_until_tomorrow(now):
        midnight = datetime.combine(now.date() + timedelta(days=1), time(0), tzinfo=UTC)
        return math.ceil((midnight - now).total_seconds())
