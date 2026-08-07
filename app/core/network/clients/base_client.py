# -*- coding: utf-8 -*-
"""
Golestoon Base Network Client.

This module defines the abstract BaseClient class inherited by all domain-specific REST clients.
It delegates all HTTP transport execution to an injected NetworkSession instance.

Architecture Layer: Layer 2 (Modular Network Sub-Clients)
Dependencies: `NetworkSession`, `ApiRoutes`, `exceptions`, `models`. NO direct `requests` import!
"""

from typing import Dict, Any, Optional, List, Union
from app.core.network.session import NetworkSession
from app.core.network.routes import ApiRoutes


class BaseClient:
    """
    Abstract base class for all domain-specific REST API clients.

    Attributes:
        session (NetworkSession): Injected HTTP transport session.
        routes (ApiRoutes): Endpoint routes registry constants.
    """

    def __init__(self, session: NetworkSession) -> None:
        if not isinstance(session, NetworkSession):
            raise TypeError("BaseClient requires a valid NetworkSession instance.")
        self._session: NetworkSession = session
        self.routes: ApiRoutes = ApiRoutes()

    @property
    def session(self) -> NetworkSession:
        """Get the underlying NetworkSession transport instance."""
        return self._session

    def _get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Execute GET request via NetworkSession."""
        return self._session.get(endpoint=endpoint, params=params, **kwargs)

    def _post(
        self,
        endpoint: str,
        data: Optional[Union[Dict[str, Any], List[Any]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Execute POST request via NetworkSession."""
        return self._session.post(endpoint=endpoint, data=data, **kwargs)

    def _put(
        self,
        endpoint: str,
        data: Optional[Union[Dict[str, Any], List[Any]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Execute PUT request via NetworkSession."""
        return self._session.put(endpoint=endpoint, data=data, **kwargs)

    def _delete(
        self,
        endpoint: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Execute DELETE request via NetworkSession."""
        return self._session.delete(endpoint=endpoint, **kwargs)
