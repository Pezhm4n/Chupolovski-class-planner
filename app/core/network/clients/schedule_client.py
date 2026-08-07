# -*- coding: utf-8 -*-
"""
Golestoon Saved Schedules Network Client.

This module provides the ScheduleClient for cloud schedule synchronization and CRUD operations (`/api/schedules`).

Architecture Layer: Layer 2 (Modular Network Sub-Clients)
Dependencies: `BaseClient`, `ScheduleModel`.
"""

from typing import List, Dict, Any, Optional
from app.core.network.clients.base_client import BaseClient
from app.core.network.models import ScheduleModel


class ScheduleClient(BaseClient):
    """
    Sub-client managing saved schedule CRUD and cloud synchronization.
    """

    def get_schedules(self) -> List[ScheduleModel]:
        """
        Fetch all cloud saved schedules for active user.

        Returns:
            List[ScheduleModel]: List of saved schedule models.
        """
        res = self._get(self.routes.SCHEDULES.BASE)
        schedules_list = res.get("schedules", res if isinstance(res, list) else [])
        return [self._parse_schedule_model(s) for s in schedules_list]

    def create_schedule(self, name: str, courses: List[Dict[str, Any]]) -> ScheduleModel:
        """
        Create a new cloud saved schedule configuration.

        Args:
            name (str): Schedule title.
            courses (List[Dict[str, Any]]): List of course objects in schedule.

        Returns:
            ScheduleModel: Created schedule model instance.
        """
        payload = {"name": name, "courses": courses}
        res = self._post(self.routes.SCHEDULES.BASE, data=payload)
        item = res.get("schedule", res)
        return self._parse_schedule_model(item)

    def update_schedule(
        self,
        schedule_id: str,
        name: str,
        courses: List[Dict[str, Any]]
    ) -> ScheduleModel:
        """
        Update an existing cloud saved schedule configuration.

        Args:
            schedule_id (str): Schedule ID.
            name (str): Updated schedule title.
            courses (List[Dict[str, Any]]): Updated courses list.

        Returns:
            ScheduleModel: Updated schedule model instance.
        """
        endpoint = self.routes.SCHEDULES.BY_ID.format(schedule_id=schedule_id)
        payload = {"name": name, "courses": courses}
        res = self._put(endpoint, data=payload)
        item = res.get("schedule", res)
        return self._parse_schedule_model(item)

    def delete_schedule(self, schedule_id: str) -> bool:
        """
        Delete a cloud saved schedule by ID.

        Args:
            schedule_id (str): Schedule ID.

        Returns:
            bool: True if deleted successfully.
        """
        endpoint = self.routes.SCHEDULES.BY_ID.format(schedule_id=schedule_id)
        self._delete(endpoint)
        return True

    def sync_schedule(self, schedule_id: str, local_courses: List[Dict[str, Any]]) -> ScheduleModel:
        """Convenience method for syncing local schedule changes to cloud."""
        return self.update_schedule(schedule_id=schedule_id, name="Synced Schedule", courses=local_courses)

    def upload_schedule(self, name: str, courses: List[Dict[str, Any]]) -> ScheduleModel:
        """Convenience method for uploading local schedule to cloud."""
        return self.create_schedule(name=name, courses=courses)

    def download_schedule(self, schedule_id: str) -> Optional[ScheduleModel]:
        """Convenience method for downloading a specific schedule by ID."""
        schedules = self.get_schedules()
        for s in schedules:
            if str(s.id) == str(schedule_id):
                return s
        return None

    def _parse_schedule_model(self, data: Dict[str, Any]) -> ScheduleModel:
        """Helper to parse API dict into ScheduleModel."""
        return ScheduleModel(
            id=str(data.get("id", "")),
            name=str(data.get("name", "Untitled Schedule")),
            courses=data.get("courses", []),
            created_at=int(data.get("created_at", 0)),
        )
