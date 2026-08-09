import json
from pathlib import Path

from app.models import NormalizedInboundEvent
from app.ingestion import InMemoryInbox


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "freight_delay.json"


def build_freight_delay_event() -> NormalizedInboundEvent:
    """Load the canonical PRD freight-delay event from the local fixture."""

    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return NormalizedInboundEvent(**payload)


def create_demo_inbox() -> InMemoryInbox:
    inbox = InMemoryInbox()
    inbox.ingest(build_freight_delay_event())
    return inbox
