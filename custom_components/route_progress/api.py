"""Asynchronous client for the Route Progress API."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout


class RouteProgressAPIError(Exception):
    """Base exception raised by the Route Progress API client."""


class RouteProgressAuthError(RouteProgressAPIError):
    """Raised when the configured bearer token is rejected."""


class RouteProgressGoneError(RouteProgressAPIError):
    """Raised when a trip has expired or has already been finished."""


class RouteProgressAPI:
    """Small aiohttp based client for the application API."""

    def __init__(
        self,
        session: ClientSession,
        base_url: str,
        token: str,
        cloudflare_client_id: str | None = None,
        cloudflare_client_secret: str | None = None,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self.base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        if cloudflare_client_id and cloudflare_client_secret:
            self._headers.update(
                {
                    "CF-Access-Client-Id": cloudflare_client_id,
                    "CF-Access-Client-Secret": cloudflare_client_secret,
                }
            )
        self._timeout = ClientTimeout(total=20)

    async def async_check_auth(self) -> None:
        """Validate connectivity and credentials without creating data."""
        await self._async_request("GET", "/api/v1/health", expected={204})

    async def async_create_trip(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a trip and return its identifiers."""
        _, content = await self._async_request(
            "POST", "/api/v1/trips", expected={201}, json=payload
        )
        if not isinstance(content, dict):
            raise RouteProgressAPIError("Create response is not a JSON object")
        if not all(key in content for key in ("trip_id", "share_url", "expires_at")):
            raise RouteProgressAPIError("Create response is missing required fields")
        return content

    async def async_get_trip(self, trip_id: str) -> dict[str, Any]:
        """Get the server-owned lifecycle state for a trip."""
        _, content = await self._async_request(
            "GET", f"/api/v1/trips/{trip_id}", expected={200}
        )
        return self._require_state(content)

    async def async_update_trip(
        self, trip_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an active trip."""
        _, content = await self._async_request(
            "POST",
            f"/api/v1/trips/{trip_id}/updates",
            expected={200},
            json=payload,
        )
        return self._require_state(content)

    async def async_accept_destination(
        self, trip_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Explicitly replace the destination of a shared trip."""
        _, content = await self._async_request(
            "POST",
            f"/api/v1/trips/{trip_id}/destination",
            expected={200},
            json=payload,
        )
        return self._require_state(content)

    async def async_finish_trip(self, trip_id: str) -> dict[str, Any] | None:
        """Finish a trip; an already absent trip is considered finished."""
        status, content = await self._async_request(
            "POST",
            f"/api/v1/trips/{trip_id}/finish",
            expected={200, 404, 410},
        )
        return self._require_state(content) if status == 200 else None

    @staticmethod
    def _require_state(content: Any) -> dict[str, Any]:
        """Validate a lifecycle response."""
        if not isinstance(content, dict) or "status" not in content:
            raise RouteProgressAPIError("Lifecycle response is invalid")
        return content

    async def _async_request(
        self,
        method: str,
        path: str,
        *,
        expected: set[int],
        json: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        """Send one request and normalize API errors."""
        try:
            async with self._session.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers,
                json=json,
                timeout=self._timeout,
            ) as response:
                if response.status in {401, 403}:
                    raise RouteProgressAuthError("API credentials were rejected")
                if response.status == 410:
                    if 410 in expected:
                        return response.status, None
                    raise RouteProgressGoneError("Trip is no longer active")
                if response.status not in expected:
                    raise RouteProgressAPIError(
                        f"Unexpected HTTP status {response.status}"
                    )

                if response.status == 204:
                    return response.status, None
                try:
                    content = await response.json(content_type=None)
                except (ValueError, ClientError):
                    content = await response.text()
                return response.status, content
        except RouteProgressAPIError:
            raise
        except (ClientError, TimeoutError) as err:
            raise RouteProgressAPIError("Could not connect to Route Progress") from err
