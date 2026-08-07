# -*- coding: utf-8 -*-
"""
Golestoon Transcript & Report 272 Network Client.

This module provides the TranscriptClient for academic transcript synchronization
and Report 272 degree requirement progress categories (`/api/transcript`).

Architecture Layer: Layer 2 (Modular Network Sub-Clients)
Dependencies: `BaseClient`, `TranscriptSyncStatusModel`.
"""

from typing import Dict, Any, List
from app.core.network.clients.base_client import BaseClient
from app.core.network.models import TranscriptSyncStatusModel


class TranscriptClient(BaseClient):
    """
    Sub-client managing student transcript sync and Report 272 degree progress.
    """

    def sync_transcript(self, student_number: str) -> TranscriptSyncStatusModel:
        """
        Trigger async background transcript sync for student.

        Args:
            student_number (str): Golestan student ID number.

        Returns:
            TranscriptSyncStatusModel: Sync job status model.
        """
        payload = {"student_number": student_number}
        res = self._post(self.routes.PROXY.TRANSCRIPT_SYNC, data=payload)
        return self._parse_sync_status(res)

    def get_degree_progress(self) -> Dict[str, Any]:
        """
        Fetch Report 272 course requirement category progress breakdown (General, Basic, Specialized, Elective).

        Returns:
            Dict[str, Any]: Degree requirements progress dictionary.
        """
        res = self._get(self.routes.PROXY.TRANSCRIPT_SYNC)
        student_data = res.get("student", res)
        return student_data.get("degree_progress", {})

    def get_semesters(self) -> List[Dict[str, Any]]:
        """
        Fetch academic transcript semesters and course grade list.

        Returns:
            List[Dict[str, Any]]: List of semester objects.
        """
        res = self._get(self.routes.PROXY.TRANSCRIPT_SYNC)
        student_data = res.get("student", res)
        return student_data.get("semesters", [])

    def _parse_sync_status(self, data: Dict[str, Any]) -> TranscriptSyncStatusModel:
        """Helper to parse API dict into TranscriptSyncStatusModel."""
        return TranscriptSyncStatusModel(
            status=str(data.get("status", "unknown")),
            message=str(data.get("message", "")),
            last_synced_at=data.get("last_synced_at"),
            is_syncing=bool(data.get("is_syncing", False)),
            job_id=data.get("job_id"),
            student=data.get("student"),
        )
