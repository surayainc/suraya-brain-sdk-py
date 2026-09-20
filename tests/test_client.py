"""Behavioral tests for BrainClient.

Exercises the real wire contract against a mocked brain (respx over httpx):
signature construction, request shaping, response parsing, and the
discriminated error model. No network is touched.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx
import pytest
import respx

from suraya_brain_sdk import (
    BrainClient,
    BrainError,
    EmitResponse,
    HealthResponse,
    ObservationInput,
    RetrieveResponse,
)

BASE_URL = "https://brain.test"
PROJECT = "suraya"
SECRET = "top-secret-hmac-key"


def _expected_sig(message: str, secret: str = SECRET) -> str:
    return hmac.new(
        secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _client(**kwargs) -> BrainClient:
    kwargs.setdefault("hmac_secret", SECRET)
    return BrainClient(BASE_URL, PROJECT, **kwargs)


# --- construction / auth-mode invariant ---------------------------------


def test_requires_exactly_one_auth_mode_none():
    with pytest.raises(ValueError, match="exactly one"):
        BrainClient(BASE_URL, PROJECT)


def test_requires_exactly_one_auth_mode_both():
    with pytest.raises(ValueError, match="exactly one"):
        BrainClient(BASE_URL, PROJECT, hmac_secret=SECRET, bootstrap_token="bt")


def test_base_url_trailing_slash_stripped():
    c = BrainClient(BASE_URL + "/", PROJECT, hmac_secret=SECRET)
    assert c.base_url == BASE_URL


# --- retrieve -----------------------------------------------------------


@respx.mock
def test_retrieve_signs_canonical_and_parses_results():
    route = respx.get(f"{BASE_URL}/api/brain/retrieve").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "node_id": "n1",
                        "scope": "project",
                        "project_slug": PROJECT,
                        "type": "decision",
                        "status": "standard",
                        "representative_summary": "did the thing",
                        "tags": ["a"],
                        "confidence": 0.9,
                        "similarity": 0.8,
                        "evidence_count": 3,
                        "last_reinforced_at": None,
                        "sample_observation_ids": ["o1"],
                    }
                ],
                "query_embedded_in_ms": 12,
                "search_in_ms": 34,
            },
        )
    )
    with _client() as c:
        resp = c.retrieve("how do we deploy", top_k=5)

    assert isinstance(resp, RetrieveResponse)
    assert len(resp.results) == 1
    assert resp.results[0].node_id == "n1"
    assert resp.query_embedded_in_ms == 12 and resp.search_in_ms == 34

    req = route.calls.last.request
    assert req.headers["X-Suraya-Signature"] == _expected_sig(f"{PROJECT}|how do we deploy|5")
    assert dict(req.url.params)["project_slug"] == PROJECT
    assert dict(req.url.params)["top_k"] == "5"
    assert "scope" not in dict(req.url.params)


@respx.mock
def test_retrieve_top_k_is_clamped_1_to_50():
    route = respx.get(f"{BASE_URL}/api/brain/retrieve").mock(
        return_value=httpx.Response(
            200, json={"results": [], "query_embedded_in_ms": 0, "search_in_ms": 0}
        )
    )
    with _client() as c:
        c.retrieve("q", top_k=999)
        assert dict(route.calls.last.request.url.params)["top_k"] == "50"
        c.retrieve("q", top_k=0)
        assert dict(route.calls.last.request.url.params)["top_k"] == "1"


@respx.mock
def test_retrieve_scope_forwarded_and_signed_with_clamped_top_k():
    route = respx.get(f"{BASE_URL}/api/brain/retrieve").mock(
        return_value=httpx.Response(
            200, json={"results": [], "query_embedded_in_ms": 0, "search_in_ms": 0}
        )
    )
    with _client() as c:
        c.retrieve("q", top_k=0, scope="shared")
    req = route.calls.last.request
    assert dict(req.url.params)["scope"] == "shared"
    # signature uses the clamped top_k (1), not the raw input
    assert req.headers["X-Suraya-Signature"] == _expected_sig(f"{PROJECT}|q|1")


# --- emit ---------------------------------------------------------------


@respx.mock
def test_emit_signs_compact_body_and_backfills_project_slug():
    route = respx.post(f"{BASE_URL}/api/brain/ingest").mock(
        return_value=httpx.Response(200, json={"observation_id": "obs-1", "status": "accepted"})
    )
    obs = ObservationInput(
        type="fix",
        representative_summary="fixed the CI",
        criticality="high",
        actor_handle="builder-backend",
    )
    with _client() as c:
        resp = c.emit_observation(obs)

    assert isinstance(resp, EmitResponse)
    assert resp.observation_id == "obs-1" and resp.status == "accepted"

    req = route.calls.last.request
    body = req.content.decode()
    # compact separators, no spaces
    assert ", " not in body and '": ' not in body
    parsed = json.loads(body)
    assert parsed["project_slug"] == PROJECT  # backfilled from client
    assert req.headers["X-Suraya-Signature"] == _expected_sig(body)
    assert req.headers["Content-Type"] == "application/json"


@respx.mock
def test_emit_preserves_explicit_project_slug():
    route = respx.post(f"{BASE_URL}/api/brain/ingest").mock(
        return_value=httpx.Response(200, json={"observation_id": "o", "status": "queued"})
    )
    obs = ObservationInput(
        type="decision",
        representative_summary="s",
        criticality="low",
        actor_handle="a",
        project_slug="other-project",
    )
    with _client() as c:
        resp = c.emit_observation(obs)
    assert resp.status == "queued"
    assert json.loads(route.calls.last.request.content.decode())["project_slug"] == "other-project"


# --- health -------------------------------------------------------------


@respx.mock
def test_health_parses_and_is_unsigned():
    route = respx.get(f"{BASE_URL}/health").mock(
        return_value=httpx.Response(200, json={"ok": True, "version": "1.2.3", "build": "abc"})
    )
    with _client() as c:
        h = c.health()
    assert isinstance(h, HealthResponse)
    assert h.ok is True and h.version == "1.2.3" and h.build == "abc"
    assert "X-Suraya-Signature" not in route.calls.last.request.headers


# --- bootstrap-token auth path -----------------------------------------


@respx.mock
def test_bootstrap_token_signature_is_prefixed():
    route = respx.get(f"{BASE_URL}/api/brain/retrieve").mock(
        return_value=httpx.Response(
            200, json={"results": [], "query_embedded_in_ms": 0, "search_in_ms": 0}
        )
    )
    with BrainClient(BASE_URL, PROJECT, bootstrap_token="ephemeral-123") as c:
        c.retrieve("q")
    assert route.calls.last.request.headers["X-Suraya-Signature"] == "bt:ephemeral-123"


# --- error model --------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (400, "validation_failed"),
        (401, "invalid_signature"),
        (404, "not_found"),
        (500, "server_error"),
    ],
)
@respx.mock
def test_error_status_maps_to_kind(status: int, kind: str):
    respx.get(f"{BASE_URL}/health").mock(return_value=httpx.Response(status, text="boom"))
    with _client() as c, pytest.raises(BrainError) as ei:
        c.health()
    assert ei.value.kind == kind
    assert ei.value.status == status


@respx.mock
def test_rate_limited_carries_retry_after():
    respx.get(f"{BASE_URL}/health").mock(
        return_value=httpx.Response(429, headers={"retry-after": "17"}, text="slow down")
    )
    with _client() as c, pytest.raises(BrainError) as ei:
        c.health()
    assert ei.value.kind == "rate_limited"
    assert ei.value.retry_after_seconds == 17


@respx.mock
def test_rate_limited_tolerates_non_integer_retry_after():
    respx.get(f"{BASE_URL}/health").mock(
        return_value=httpx.Response(429, headers={"retry-after": "not-a-number"})
    )
    with _client() as c, pytest.raises(BrainError) as ei:
        c.health()
    assert ei.value.kind == "rate_limited"
    assert ei.value.retry_after_seconds is None


@respx.mock
def test_success_with_non_json_body_raises_server_error():
    respx.get(f"{BASE_URL}/health").mock(
        return_value=httpx.Response(200, text="<html>not json</html>")
    )
    with _client() as c, pytest.raises(BrainError) as ei:
        c.health()
    assert ei.value.kind == "server_error"
