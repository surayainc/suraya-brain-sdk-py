"""BrainClient — Python client for the Suraya brain HTTP API.

Mirrors the TypeScript @surayaorg/brain-sdk surface. Synchronous + async
flavors share the same signature shapes.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict
from typing import Any, Optional, Union

import httpx

from .types import (
    BrainError,
    EmitResponse,
    HealthResponse,
    ObservationInput,
    RetrieveResponse,
    RetrieveResult,
)

SIGNATURE_HEADER = "X-Suraya-Signature"


class BrainClient:
    """Synchronous Suraya brain client.

    Pass exactly one of hmac_secret or bootstrap_token. The HMAC path is
    long-lived per-project service-to-service auth; the bootstrap-token
    path is for F6-sealed ephemeral device-bound auth.
    """

    def __init__(
        self,
        base_url: str,
        project_slug: str,
        *,
        hmac_secret: Optional[str] = None,
        bootstrap_token: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        if (hmac_secret is None) == (bootstrap_token is None):
            raise ValueError(
                "BrainClient requires exactly one of hmac_secret or bootstrap_token"
            )
        self.base_url = base_url.rstrip("/")
        self.project_slug = project_slug
        self._hmac_secret = hmac_secret
        self._bootstrap_token = bootstrap_token
        self._client = httpx.Client(timeout=timeout)

    def __enter__(self) -> "BrainClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def retrieve(
        self,
        q: str,
        top_k: int = 10,
        scope: Optional[str] = None,
    ) -> RetrieveResponse:
        top_k = max(1, min(50, int(top_k)))
        canonical = f"{self.project_slug}|{q}|{top_k}"
        sig = self._sign(canonical)
        params: dict[str, str] = {
            "q": q,
            "project_slug": self.project_slug,
            "top_k": str(top_k),
        }
        if scope:
            params["scope"] = scope
        res = self._client.get(
            f"{self.base_url}/api/brain/retrieve",
            params=params,
            headers={SIGNATURE_HEADER: sig, "Accept": "application/json"},
        )
        data = self._handle(res, "retrieve")
        return RetrieveResponse(
            results=[RetrieveResult(**r) for r in data.get("results", [])],
            query_embedded_in_ms=int(data.get("query_embedded_in_ms", 0)),
            search_in_ms=int(data.get("search_in_ms", 0)),
        )

    def emit_observation(self, obs: ObservationInput) -> EmitResponse:
        payload = asdict(obs)
        if not payload.get("project_slug"):
            payload["project_slug"] = self.project_slug
        body = json.dumps(payload, separators=(",", ":"))
        sig = self._sign(body)
        res = self._client.post(
            f"{self.base_url}/api/brain/ingest",
            content=body,
            headers={
                "Content-Type": "application/json",
                SIGNATURE_HEADER: sig,
            },
        )
        data = self._handle(res, "emit")
        return EmitResponse(
            observation_id=str(data.get("observation_id", "")),
            status=data.get("status", "accepted"),
        )

    def health(self) -> HealthResponse:
        res = self._client.get(
            f"{self.base_url}/health", headers={"Accept": "application/json"}
        )
        data = self._handle(res, "health")
        return HealthResponse(
            ok=bool(data.get("ok", False)),
            version=str(data.get("version", "")),
            build=str(data.get("build", "")),
        )

    # --- internals ---

    def _sign(self, message: str) -> str:
        if self._bootstrap_token is not None:
            return f"bt:{self._bootstrap_token}"
        assert self._hmac_secret is not None
        digest = hmac.new(
            self._hmac_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return digest

    @staticmethod
    def _handle(res: httpx.Response, op: str) -> dict[str, Any]:
        if res.is_success:
            try:
                return res.json()
            except Exception as err:
                raise BrainError(
                    "server_error",
                    f"{op}: response not JSON: {err}",
                    status=res.status_code,
                ) from err

        retry_after = None
        ra = res.headers.get("retry-after")
        if ra:
            try:
                retry_after = int(ra)
            except ValueError:
                retry_after = None

        body_preview = (res.text or "")[:300]
        if res.status_code == 400:
            raise BrainError("validation_failed", f"{op}: {body_preview}", status=400)
        if res.status_code == 401:
            raise BrainError("invalid_signature", f"{op}: invalid signature", status=401)
        if res.status_code == 404:
            raise BrainError("not_found", f"{op}: not found", status=404)
        if res.status_code == 429:
            raise BrainError(
                "rate_limited",
                f"{op}: rate limited",
                status=429,
                retry_after_seconds=retry_after,
            )
        raise BrainError(
            "server_error",
            f"{op}: {res.status_code} {body_preview}",
            status=res.status_code,
        )
