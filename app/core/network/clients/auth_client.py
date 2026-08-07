# -*- coding: utf-8 -*-
"""
Golestoon Authentication Network Client.

This module provides the AuthClient for user login, account registration,
token validation, and user profile retrieval endpoints (`/api/auth/*`).

Architecture Layer: Layer 2 (Modular Network Sub-Clients)
Dependencies: `BaseClient`, `AuthResponseModel`, `UserModel`, `UserMetadataModel`.
"""

from typing import Dict, Any, Optional
from app.core.network.clients.base_client import BaseClient
from app.core.network.models import AuthResponseModel, UserModel, UserMetadataModel


class AuthClient(BaseClient):
    """
    Sub-client managing authentication and user account operations.
    """

    def login(self, email: str, password: str) -> AuthResponseModel:
        """
        Authenticate user with email and password.

        Args:
            email (str): User account email.
            password (str): User account password.

        Returns:
            AuthResponseModel: Auth response containing JWT token and user profile model.
        """
        payload = {"email": email, "password": password}
        res = self._post(self.routes.AUTH.LOGIN, data=payload)
        return self._parse_auth_response(res)

    def signup(self, full_name: str, email: str, password: str) -> AuthResponseModel:
        """
        Register a new user account.

        Args:
            full_name (str): User full name.
            email (str): User account email.
            password (str): User account password.

        Returns:
            AuthResponseModel: Auth response containing JWT token and user profile model.
        """
        payload = {"full_name": full_name, "email": email, "password": password}
        res = self._post(self.routes.AUTH.SIGNUP, data=payload)
        return self._parse_auth_response(res)

    def get_me(self) -> UserModel:
        """
        Fetch active authenticated user profile.

        Returns:
            UserModel: User profile model.
        """
        res = self._get(self.routes.AUTH.ME)
        user_data = res.get("user", res)
        return self._parse_user_model(user_data)

    def logout(self) -> bool:
        """
        Client-side session logout. Purges local token state.

        Returns:
            bool: Always True upon clearing token manager session.
        """
        if self._session.token_manager:
            self._session.token_manager.clear_token()
        return True

    def validate_token(self) -> bool:
        """
        Validate currently active token against backend server.

        Returns:
            bool: True if token is valid and active, False otherwise.
        """
        try:
            self.get_me()
            return True
        except Exception:
            return False

    def refresh_token(self) -> bool:
        """
        Placeholder for future server-side token refresh claims.

        Returns:
            bool: True if refreshed successfully.
        """
        return self.validate_token()

    def _parse_auth_response(self, data: Dict[str, Any]) -> AuthResponseModel:
        """Helper to parse API JSON dict into AuthResponseModel."""
        token = data.get("token", "")
        user_dict = data.get("user", {})
        user_model = self._parse_user_model(user_dict)
        return AuthResponseModel(token=token, user=user_model)

    def _parse_user_model(self, data: Dict[str, Any]) -> UserModel:
        """Helper to parse user dict into UserModel."""
        meta_dict = data.get("user_metadata", data.get("metadata", {}))
        meta = UserMetadataModel(
            full_name=meta_dict.get("full_name"),
            google_id=meta_dict.get("google_id"),
            avatar=meta_dict.get("avatar"),
            password_set=meta_dict.get("password_set", True),
            auth_methods=meta_dict.get("auth_methods", []),
            has_contributed=meta_dict.get("has_contributed", False),
            review_count=meta_dict.get("review_count", 0),
        )
        return UserModel(
            id=str(data.get("id", "")),
            email=data.get("email", ""),
            user_metadata=meta,
        )
