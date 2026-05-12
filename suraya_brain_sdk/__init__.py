"""Python client for the Suraya brain.

Sister package to the TypeScript @surayaorg/brain-sdk. Same wire contract;
same HMAC signing scheme; same discriminated error model. MIT licensed.
"""

from .client import BrainClient
from .types import (
    BrainError,
    ObservationInput,
    ObservationType,
    Criticality,
    MemoryNodeScope,
    MemoryNodeStatus,
    RetrieveResult,
    RetrieveResponse,
    EmitResponse,
    HealthResponse,
)

__all__ = [
    "BrainClient",
    "BrainError",
    "ObservationInput",
    "ObservationType",
    "Criticality",
    "MemoryNodeScope",
    "MemoryNodeStatus",
    "RetrieveResult",
    "RetrieveResponse",
    "EmitResponse",
    "HealthResponse",
]

__version__ = "0.1.0"
