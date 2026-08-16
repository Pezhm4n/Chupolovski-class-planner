# -*- coding: utf-8 -*-
"""
Golestoon Scraper & Proxy Network Client.

This module provides the ProxyClient for routing catalog queries and remote Golestan operations
through Golestoon's cloud backend proxy endpoints (`/scraper-proxy/*`).

Architecture Layer: Layer 2 (Modular Network Sub-Clients)
Dependencies: `BaseClient`. NO local scraping imports!
"""

from typing import List, Dict, Any, Optional
from app.core.network.clients.base_client import BaseClient


class ProxyClient(BaseClient):
    """
    Sub-client managing backend proxy operations for course catalogs and student profile queries.
    """

    def fetch_all_courses(
        self,
        department: str = "",
        availability: str = "both"
    ) -> List[Dict[str, Any]]:
        """
        Fetch full course catalog from backend proxy cache.

        Args:
            department (str): Optional department filter.
            availability (str): 'available', 'unavailable', or 'both'.

        Returns:
            List[Dict[str, Any]]: List of course dictionary objects.
        """
        params = {"department": department, "availability": availability}
        res = self._get(self.routes.PROXY.COURSES_ALL, params=params, is_proxy=True)
        if isinstance(res, list):
            # Flat catalog (hierarchy=false) — NetworkSession wraps bare JSON
            # arrays as {"data": [...]}; accept both shapes.
            return res
        if isinstance(res, dict):
            return res.get("courses") or res.get("data") or []
        return []

    def fetch_student_profile(
        self,
        golestan_user: str,
        golestan_pass: str
    ) -> Dict[str, Any]:
        """
        Query student academic profile from Golestan via backend secure proxy.

        Args:
            golestan_user (str): University student ID.
            golestan_pass (str): University Golestan password.

        Returns:
            Dict[str, Any]: Parsed student profile data.
        """
        headers = {
            "x-username": golestan_user,
            "x-password": golestan_pass,
        }
        return self._get(self.routes.PROXY.STUDENT_PROFILE, headers=headers, is_proxy=True)

    def send_proxy_request(
        self,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generic proxy transport execution for future cloud backend features.

        Args:
            endpoint (str): Target proxy sub-path.
            payload (Optional[Dict[str, Any]]): Request payload.

        Returns:
            Dict[str, Any]: Server proxy JSON response.
        """
        return self._post(endpoint, data=payload, is_proxy=True)
