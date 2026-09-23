"""Small process-wide public-demo budgets; no visitor/IP map or forwarded-IP trust."""

import math
import re
import threading
import time
from dataclasses import dataclass

PUBLIC_QUESTIONS = ("What most likely happened?", "What malware family was used?")
PUBLIC_ANALYSIS_PATH = re.compile(r"/api/incidents/[A-Za-z0-9-]{1,80}/analysis")
PUBLIC_SCENARIO_ANALYSIS_PATH = re.compile(
    r"/api/scenarios/[a-z][a-z0-9-]{0,59}/analysis/(summary|malware)"
)


@dataclass
class Bucket:
    capacity: int
    per_minute: int
    tokens: float
    updated: float


class PublicBudget:
    """Fixed five buckets, at most eight active requests and two analyst requests.

    Limits apply across all visitors of one process. They restart with the process
    and do not coordinate multiple replicas. Edge protection is still required
    for large traffic floods. No client-provided identity bypasses these limits.
    """

    LIMITS = {
        "all": (100, 300),
        "read": (60, 240),
        "search": (20, 60),
        "analysis": (4, 12),
        "health": (10, 60),
    }

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.Lock()
        now = clock()
        self.buckets = {
            name: Bucket(capacity, per_minute, capacity, now)
            for name, (capacity, per_minute) in self.LIMITS.items()
        }
        self.active = 0
        self.active_analysis = 0

    @staticmethod
    def category(method: str, path: str) -> str:
        if method == "POST" and PUBLIC_ANALYSIS_PATH.fullmatch(path):
            return "analysis"
        if method in {"GET", "HEAD"} and PUBLIC_SCENARIO_ANALYSIS_PATH.fullmatch(path):
            return "analysis"
        if path in {"/health", "/ready"}:
            return "health"
        if path == "/api/events":
            return "search"
        return "read"

    def enter(self, category: str) -> tuple[int, int] | None:
        with self.lock:
            now = self.clock()
            buckets = [self.buckets["all"], self.buckets[category]]
            for bucket in buckets:
                bucket.tokens = min(
                    bucket.capacity,
                    bucket.tokens + max(0, now - bucket.updated) * bucket.per_minute / 60,
                )
                bucket.updated = now
            if any(bucket.tokens < 1 for bucket in buckets):
                retry = max(
                    math.ceil((1 - bucket.tokens) * 60 / bucket.per_minute) for bucket in buckets
                )
                return 429, max(1, retry)
            if self.active >= 8 or (category == "analysis" and self.active_analysis >= 2):
                return 503, 1
            for bucket in buckets:
                bucket.tokens -= 1
            self.active += 1
            self.active_analysis += category == "analysis"
        return None

    def leave(self, category: str) -> None:
        with self.lock:
            self.active -= 1
            self.active_analysis -= category == "analysis"
