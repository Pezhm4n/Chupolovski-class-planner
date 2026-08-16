# -*- coding: utf-8 -*-
"""
Golestoon Authentication Network Client.

Implements the exact backend auth surface of `golestan-web/server/index.ts`:

  POST /api/auth/signup          {full_name, email, password} → {token, user}
  POST /api/auth/login           {email, password}            → {token, user}
  PUT  /api/auth/profile         (JWT) {fullName, currentPassword, newPassword}
  POST /api/auth/forgot-password {email}                      → message
  POST /api/auth/reset-password  {token, newPassword}         → message
  POST /api/auth/set-password    (JWT) {password}

NOTE: the backend deliberately exposes **no** `GET /api/auth/me` endpoint —
the authenticated user model is returned inline by login/signup responses
and tokens are validated implicitly through auth-protected endpoints
(`GET /api/schedules` is used here as the lightweight probe, mirroring the
web client's 401-driven session handling).

Architecture Layer: Layer 2 (Modular Network Sub-Clients)
Dependencies: `BaseClient`, `AuthResponseModel`, `UserModel`.
"""

import logging
from typing import Any, Dict, Optional

from app.core.network.clients.base_client import BaseClient
from app.core.network.models import AuthResponseModel, UserModel
from app.core.network.exceptions import GolestoonNetworkError, AuthenticationError

logger = logging.getLogger("golestoon.network.auth_client")


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
            full_name (str): User full name (sent as `fullName`; 3-100 chars).
            email (str): User account email.
            password (str): User account password.

        Returns:
            AuthResponseModel: Auth response containing JWT token and user profile model.
        """
        payload = {"fullName": full_name, "email": email, "password": password}
        res = self._post(self.routes.AUTH.SIGNUP, data=payload)
        return self._parse_auth_response(res)

    def update_profile(
        self,
        full_name: Optional[str] = None,
        current_password: Optional[str] = None,
        new_password: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update the authenticated user's profile / change password.

        Args:
            full_name: New display name.
            current_password: Current password (required for password change).
            new_password: New password to set.

        Returns:
            Dict[str, Any]: Server confirmation payload.
        """
        payload: Dict[str, Any] = {}
        if full_name:
            payload["fullName"] = full_name
        if new_password:
            payload["newPassword"] = new_password
            if current_password:
                payload["currentPassword"] = current_password
        res = self._put(self.routes.AUTH.UPDATE_PROFILE, data=payload)
        return res

    def forgot_password(self, email: str) -> Dict[str, Any]:
        """
        Request a password-reset email.

        Returns:
            Dict[str, Any]: Server response (always 200-shaped for privacy).
        """
        return self._post(self.routes.AUTH.FORGOT_PASSWORD, data={"email": email})

    def reset_password(self, reset_token: str, new_password: str) -> Dict[str, Any]:
        """
        Consume a reset token (emailed link) and set a new password.

        Returns:
            Dict[str, Any]: Server confirmation payload.
        """
        return self._post(
            self.routes.AUTH.RESET_PASSWORD,
            data={"token": reset_token, "newPassword": new_password},
        )

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
        Validate the stored JWT against a lightweight auth-protected endpoint
        (`GET /api/schedules`). The backend has no dedicated /me route — this
        mirrors the web client's implicit 401-driven validation.

        Returns:
            bool: True if the token is accepted by the server.
        """
        try:
            self._get(self.routes.SCHEDULES.BASE, timeout=(5, 15))
            return True
        except AuthenticationError:
            return False
        except GolestoonNetworkError as err:
            logger.warning("Token validation probe failed: %s", err)
            return False

    # ─────────────────────────────────────────────────────────
    # Parsing helpers
    # ─────────────────────────────────────────────────────────

    def _parse_auth_response(self, data: Dict[str, Any]) -> AuthResponseModel:
        """Helper to parse API JSON dict into AuthResponseModel."""
        token = data.get("token", "")
        user_dict = data.get("user", {})
        user_model = self._parse_user_model(user_dict)
        return AuthResponseModel(token=token, user=user_model)

    def _parse_user_model(self, data: Dict[str, Any]) -> UserModel:
        """Helper to parse user dict into UserModel."""
        from app.core.network.models import UserMetadataModel
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
