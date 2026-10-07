"""Typed dataclasses for the Suraya brain SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ObservationType = Literal[
    "decision",
    "failure",
    "fix",
    "style",
    "deviation",
    "correction",
    "scope_state",
]

Criticality = Literal["low", "medium", "high"]
MemoryNodeScope = Literal["project", "shared"]
MemoryNodeStatus = Literal["draft", "proposed", "standard", "historic"]


@dataclass
class RetrieveResult:
    node_id: str
    scope: MemoryNodeScope
    project_slug: str | None
    type: ObservationType
    status: MemoryNodeStatus
    representative_summary: str
    tags: list[str]
    confidence: float
    similarity: float
    evidence_count: int
    last_reinforced_at: str | None
    sample_observation_ids: list[str]


@dataclass
class RetrieveResponse:
    results: list[RetrieveResult]
    query_embedded_in_ms: int
    search_in_ms: int


@dataclass
class ObservationInput:
    type: ObservationType
    representative_summary: str
    criticality: Criticality
    actor_handle: str
    project_slug: str | None = None
    tags: list[str] = field(default_factory=list)
    linked_observation_ids: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    validity_start: str | None = None
    validity_end: str | None = None


@dataclass
class EmitResponse:
    observation_id: str
    status: Literal["accepted", "queued"]


@dataclass
class HealthResponse:
    ok: bool
    version: str
    build: str


BrainErrorKind = Literal[
    "invalid_signature",
    "rate_limited",
    "not_found",
    "network",
    "server_error",
    "validation_failed",
]


class BrainError(Exception):
    """Raised on any brain-side failure. Inspect .kind to disambiguate."""

    def __init__(
        self,
        kind: BrainErrorKind,
        message: str,
        status: int | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status
        self.retry_after_seconds = retry_after_seconds
