"""Python client for the Suraya brain.

Sister package to the TypeScript @surayaorg/brain-sdk. Same wire contract;
same HMAC signing scheme; same discriminated error model. MIT licensed.
"""

from .client import BrainClient
from .types import (
    BrainError,
    Criticality,
    EmitResponse,
    HealthResponse,
    MemoryNodeScope,
    MemoryNodeStatus,
    ObservationInput,
    ObservationType,
    RetrieveResponse,
    RetrieveResult,
)

__all__ = [
    "BrainClient",
    "BrainError",
    "Criticality",
    "EmitResponse",
    "HealthResponse",
    "MemoryNodeScope",
    "MemoryNodeStatus",
    "ObservationInput",
    "ObservationType",
    "RetrieveResponse",
    "RetrieveResult",
]

__version__ = "0.1.0"
