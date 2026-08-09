from dataclasses import dataclass
from typing import Literal


Connector = Literal["gmail", "microsoft_graph", "front", "whatsapp"]
RequestType = Literal["shipment_delay", "unknown"]
Priority = Literal["low", "normal", "high", "urgent", "unknown"]


@dataclass(frozen=True)
class Classification:
    """Typed deterministic classification exposed by the fixture path."""

    request_type: RequestType
    priority: Priority
    confidence: float
    rationale: str
    evidence_message_ids: list[str]

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("classification confidence must be between 0 and 1")


@dataclass(frozen=True)
class NormalizedInboundEvent:
    """Provider-neutral inbound event matching the PRD contract."""

    event_id: str
    connector: Connector
    workspace_id: str
    provider_account_id: str
    provider_thread_id: str
    provider_message_id: str
    occurred_at: str
    received_at: str
    direction: Literal["inbound", "outbound"]
    sender: dict[str, str | None]
    recipients: list[dict[str, str | None]]
    subject: str | None
    body_text: str
    body_html: str | None
    attachments: list[dict[str, str | int]]
    raw_reference: str


@dataclass(frozen=True)
class IngestResult:
    accepted: bool
    duplicate: bool
    conversation_id: str
    duplicate_reason: str | None = None
