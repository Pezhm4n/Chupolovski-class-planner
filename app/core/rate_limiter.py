# -*- coding: utf-8 -*-
"""
Golestan Rate Limiter & Sync Protection Module.

Enforces security and load-control policies:
1. Distinct Accounts Rate Limiter: Allows at most 3 distinct/new student IDs
   to sync within a sliding 10-minute window. A 4th distinct ID is blocked
   until the oldest account falls outside the window.
2. Per-Account Refresh Cooldown: Requires a minimum 10-minute interval between
   consecutive transcript syncs for the same student ID.

Architecture Layer: Layer 1 / Core Service
Dependencies: Python Standard Library (json, os, time, threading, pathlib).
"""

import json
import os
import time
import logging
from pathlib import Path
from threading import Lock
from typing import Tuple, Dict, Any, List, Optional

logger = logging.getLogger("golestoon.rate_limiter")

RATE_LIMIT_FILE = Path(__file__).resolve().parent.parent / "data" / "rate_limit.json"

DISTINCT_ACCOUNTS_LIMIT = 3
DISTINCT_ACCOUNTS_WINDOW_SECONDS = 600  # 10 minutes
SINGLE_ACCOUNT_COOLDOWN_SECONDS = 600   # 10 minutes


class GolestanRateLimiter:
    """
    Thread-safe and persisted rate limiter for Golestan university queries.
    """

    _instance: Optional["GolestanRateLimiter"] = None
    _instance_lock = Lock()

    def __init__(self, storage_file: Optional[Path] = None) -> None:
        self._file = storage_file or RATE_LIMIT_FILE
        self._lock = Lock()
        self._data: Dict[str, Any] = {
            "recent_accounts": [],       # List of {"student_id": str, "timestamp": float}
            "last_sync_per_student": {},  # Dict[student_id, timestamp]
        }
        self._load()

    @classmethod
    def get_instance(cls) -> "GolestanRateLimiter":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _load(self) -> None:
        """Load state from local storage JSON file safely."""
        try:
            if self._file.exists():
                with open(self._file, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    if isinstance(content, dict):
                        self._data["recent_accounts"] = content.get("recent_accounts", [])
                        self._data["last_sync_per_student"] = content.get("last_sync_per_student", {})
        except Exception as e:
            logger.warning("Could not load rate limiter file: %s", e)

    def _save(self) -> None:
        """Persist state to local storage JSON file safely."""
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._file.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            temp_path.replace(self._file)
        except Exception as e:
            logger.error("Could not save rate limiter file: %s", e)

    def _cleanup_expired_entries(self, now: float) -> None:
        """Remove account entries older than the sliding window."""
        cutoff = now - DISTINCT_ACCOUNTS_WINDOW_SECONDS
        self._data["recent_accounts"] = [
            entry for entry in self._data["recent_accounts"]
            if entry.get("timestamp", 0) > cutoff
        ]

    def check_distinct_account_allowed(self, student_id: str) -> Tuple[bool, int]:
        """
        Check if a student ID is permitted to sync under the distinct accounts rule.

        Rules:
        - If the student ID was already used in the active 10-minute window (repeat account),
          it is allowed without consuming a new slot.
        - If it is a new/distinct student ID, it is allowed if fewer than 3 distinct
          accounts have been active in the last 10 minutes.
        - Otherwise, it is blocked with remaining seconds until the oldest distinct account expires.

        Returns:
            (allowed: bool, wait_seconds: int)
        """
        if not student_id or not str(student_id).strip():
            return False, DISTINCT_ACCOUNTS_WINDOW_SECONDS

        sid = str(student_id).strip()
        now = time.time()

        with self._lock:
            self._cleanup_expired_entries(now)
            
            # Find unique active student IDs in window
            active_sids = set()
            oldest_timestamp = now
            for entry in self._data["recent_accounts"]:
                entry_sid = entry.get("student_id")
                entry_ts = entry.get("timestamp", now)
                if entry_sid:
                    active_sids.add(entry_sid)
                    if entry_ts < oldest_timestamp:
                        oldest_timestamp = entry_ts

            # Case A: Same account (already active in window) -> Allowed
            if sid in active_sids:
                return True, 0

            # Case B: New account and fewer than 3 distinct accounts active -> Allowed
            if len(active_sids) < DISTINCT_ACCOUNTS_LIMIT:
                return True, 0

            # Case C: 4th distinct account attempted -> Blocked with cooldown
            elapsed_since_oldest = now - oldest_timestamp
            remaining = max(1, int(DISTINCT_ACCOUNTS_WINDOW_SECONDS - elapsed_since_oldest))
            return False, remaining

    def check_student_refresh_allowed(self, student_id: str) -> Tuple[bool, int]:
        """
        Check if an existing student ID is permitted to refresh (10-minute cooldown).

        Returns:
            (allowed: bool, wait_seconds: int)
        """
        if not student_id or not str(student_id).strip():
            return False, SINGLE_ACCOUNT_COOLDOWN_SECONDS

        sid = str(student_id).strip()
        now = time.time()

        with self._lock:
            last_sync = self._data["last_sync_per_student"].get(sid)
            if last_sync is None:
                return True, 0

            elapsed = now - float(last_sync)
            if elapsed >= SINGLE_ACCOUNT_COOLDOWN_SECONDS:
                return True, 0

            remaining = max(1, int(SINGLE_ACCOUNT_COOLDOWN_SECONDS - elapsed))
            return False, remaining

    def record_account_sync(self, student_id: str) -> None:
        """
        Record a successful sync event for a student ID.
        """
        if not student_id or not str(student_id).strip():
            return

        sid = str(student_id).strip()
        now = time.time()

        with self._lock:
            self._cleanup_expired_entries(now)
            self._data["recent_accounts"].append({
                "student_id": sid,
                "timestamp": now,
            })
            self._data["last_sync_per_student"][sid] = now
            self._save()

    def get_last_sync_time(self, student_id: str) -> Optional[float]:
        """Return the timestamp of the last successful sync for a student."""
        sid = str(student_id).strip()
        with self._lock:
            return self._data["last_sync_per_student"].get(sid)


# Global singleton instance
rate_limiter = GolestanRateLimiter.get_instance()
