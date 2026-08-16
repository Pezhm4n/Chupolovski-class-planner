# -*- coding: utf-8 -*-
"""
Golestoon Transcript & Report 272 Network Client.

This module provides the TranscriptClient implementing the exact backend
contract of `golestan-web/server/index.ts`:

  POST /api/transcript/sync   (JWT-protected)
      Headers : x-username / x-password  (Golestan university credentials)
      Body    : {mode: 'full'|'recent', wait: bool, force: bool}
      Returns : {status: done|queued|syncing|too_recent|needs_login|error,
                 student: <full record when wait=true & done>, lastSyncedAt, ...}

  GET /api/transcript         (JWT-protected)
      Returns : {lastSyncedAt, isSyncing, status: 'ok',
                 syncProgress: 0-100, syncStep: str|null}   — metadata ONLY.

Architecture Layer: Layer 2 (Modular Network Sub-Clients)
Dependencies: `BaseClient`, `TranscriptSyncStatusModel`.
"""

from typing import Dict, Any, Optional, Tuple

from app.core.network.clients.base_client import BaseClient
from app.core.network.models import TranscriptSyncStatusModel

# Full sync with wait=true performs server-side scraping of every semester;
# the web client allows 35s — desktop uses a generous read timeout so slow
# Golestan responses don't abort the request prematurely.
SYNC_TIMEOUT: Tuple[int, int] = (10, 120)
STATUS_TIMEOUT: Tuple[int, int] = (5, 15)


class TranscriptClient(BaseClient):
    """
    Sub-client managing student transcript sync and Report 272 degree progress.
    """

    def trigger_sync(
        self,
        golestan_username: str,
        golestan_password: str,
        mode: str = "full",
        wait: bool = True,
        force: bool = False,
    ) -> TranscriptSyncStatusModel:
        """
        Trigger a transcript sync job on the backend.

        Args:
            golestan_username (str): University student ID (x-username header).
            golestan_password (str): University Golestan password (x-password header).
            mode (str): 'full' (all semesters + Report 272) or 'recent'.
            wait (bool): When True, blocks until the job finishes and the
                response carries the complete `student` record.
            force (bool): Bypass the client-visible 10-minute freshness window.

        Returns:
            TranscriptSyncStatusModel: Parsed sync status (see module docstring).
        """
        headers = {
            "x-username": golestan_username,
            "x-password": golestan_password,
        }
        payload = {
            "mode": "full" if mode == "full" else "recent",
            "wait": bool(wait),
            "force": bool(force),
        }
        res = self._post(
            self.routes.PROXY.TRANSCRIPT_SYNC,
            data=payload,
            headers=headers,
            timeout=SYNC_TIMEOUT,
        )
        return self._parse_sync_response(res)

    def get_sync_status(self) -> TranscriptSyncStatusModel:
        """
        Fetch sync metadata (lastSyncedAt / isSyncing / progress / step).

        Note: this endpoint never returns transcript data itself — the full
        student record is only delivered by `trigger_sync(wait=True)`.
        """
        res = self._get(self.routes.PROXY.TRANSCRIPT_STATUS, timeout=STATUS_TIMEOUT)
        return TranscriptSyncStatusModel(
            status=str(res.get("status", "unknown")),
            message="",
            last_synced_at=res.get("lastSyncedAt"),
            is_syncing=bool(res.get("isSyncing", False)),
            sync_progress=int(res.get("syncProgress", 0) or 0),
            sync_step=res.get("syncStep"),
        )

    # ─────────────────────────────────────────────────────────
    # Response parsing helpers
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def _parse_sync_response(res: Dict[str, Any]) -> TranscriptSyncStatusModel:
        """Map the POST /api/transcript/sync JSON payload to the status DTO."""
        minutes_left = res.get("minutesLeft")
        return TranscriptSyncStatusModel(
            status=str(res.get("status", "unknown")),
            message=str(res.get("message", "")),
            last_synced_at=res.get("lastSyncedAt"),
            is_syncing=bool(res.get("isSyncing", False)),
            sync_progress=100 if res.get("status") == "done" else 0,
            sync_step=None,
            minutes_left=int(minutes_left) if minutes_left is not None else None,
            mode=res.get("mode"),
            student=res.get("student") if isinstance(res.get("student"), dict) else None,
        )
