from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.fixture import build_freight_delay_event, create_demo_inbox
from app.ingestion import (
    ApprovalRequiredError,
    ConversationNotFoundError,
    EvidenceRequiredError,
    InMemoryInbox,
    ResourceNotFoundError,
    VersionConflictError,
)


class AiRunRequest(BaseModel):
    action: Literal[
        "classify",
        "classify_and_route",
        "route",
        "extract",
        "retrieve",
        "summarize",
        "draft",
    ]
    workspace_id: str = "demo-workspace"


class AssignmentRequest(BaseModel):
    workspace_id: str = "demo-workspace"
    owner_id: str | None = None
    queue_id: str | None = None
    expected_version: int = Field(ge=1)
    actor_id: str = Field(min_length=1)


class ClaimRequest(BaseModel):
    workspace_id: str = "demo-workspace"
    expected_version: int = Field(ge=1)
    actor_id: str = Field(min_length=1)


class CommentRequest(BaseModel):
    workspace_id: str = "demo-workspace"
    body: str = Field(min_length=1, max_length=4000)
    actor_id: str = Field(min_length=1)
    client_request_id: str | None = Field(default=None, min_length=1)
    expected_version: int = Field(ge=1)


class DraftEditRequest(BaseModel):
    workspace_id: str = "demo-workspace"
    body: str = Field(min_length=1, max_length=12000)
    actor_id: str = Field(min_length=1)
    expected_version: int = Field(ge=1)


class DraftApprovalRequest(BaseModel):
    workspace_id: str = "demo-workspace"
    actor_id: str = Field(min_length=1)
    expected_version: int = Field(ge=1)


class DraftSendRequest(BaseModel):
    workspace_id: str = "demo-workspace"
    actor_id: str = Field(min_length=1)
    approval_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1, max_length=200)


class SyncRequest(BaseModel):
    kind: Literal["inbound"] = "inbound"
    idempotency_key: str = Field(min_length=1, max_length=200)
    failure_mode: Literal["transient", "permanent"] | None = None


class SlaStartRequest(BaseModel):
    workspace_id: str = "demo-workspace"
    actor_id: str = Field(min_length=1)
    expected_version: int = Field(ge=1)


class SlaEvaluateRequest(BaseModel):
    workspace_id: str = "demo-workspace"
    now: str = Field(min_length=1)


class ResolveRequest(BaseModel):
    workspace_id: str = "demo-workspace"
    actor_id: str = Field(min_length=1)
    expected_version: int = Field(ge=1)


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    fields: dict[str, str] | None = None,
    extra: dict[str, object] | None = None,
) -> JSONResponse:
    content: dict[str, object] = {
        "code": code,
        "message": message,
        "requestId": str(uuid4()),
        "retryable": False,
    }
    if fields:
        content["fields"] = fields
    if extra:
        content.update(extra)
    return JSONResponse(status_code=status_code, content=content)


def create_app(inbox: InMemoryInbox | None = None) -> FastAPI:
    fixed_repository = inbox
    demo_workspace = "demo-workspace"
    seeded_conversation_id = "conversation-ft-204"

    def get_repository() -> InMemoryInbox:
        if fixed_repository is not None:
            return fixed_repository
        return demo_inbox

    application = FastAPI(
        title="AI Shared Inbox Customer Operations Copilot",
        version="0.2.0-fixture",
        description="Fixture-first local surface; no live provider or queue is configured.",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3103",
            "http://127.0.0.1:3103",
        ],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        del request
        code = "not_found" if exc.status_code == 404 else "internal_error"
        return _error_response(
            status_code=exc.status_code,
            code=code,
            message=str(exc.detail),
        )

    @application.exception_handler(ConversationNotFoundError)
    async def conversation_not_found_handler(
        request: Request,
        exc: ConversationNotFoundError,
    ) -> JSONResponse:
        del request
        return _error_response(
            status_code=404,
            code="not_found",
            message="conversation_not_found",
        )

    @application.exception_handler(VersionConflictError)
    async def version_conflict_handler(
        request: Request,
        exc: VersionConflictError,
    ) -> JSONResponse:
        del request
        return _error_response(
            status_code=409,
            code="version_conflict",
            message="conversation_version_conflict",
            fields={
                "expected_version": str(exc.expected_version),
                "current_version": str(exc.current_version),
            },
            extra={"currentVersion": exc.current_version},
        )

    @application.exception_handler(ResourceNotFoundError)
    async def resource_not_found_handler(
        request: Request,
        exc: ResourceNotFoundError,
    ) -> JSONResponse:
        del request, exc
        return _error_response(
            status_code=404,
            code="not_found",
            message="draft_not_found",
        )

    @application.exception_handler(ApprovalRequiredError)
    async def approval_required_handler(
        request: Request,
        exc: ApprovalRequiredError,
    ) -> JSONResponse:
        del request
        return _error_response(
            status_code=409,
            code="approval_required",
            message=str(exc),
        )

    @application.exception_handler(EvidenceRequiredError)
    async def evidence_required_handler(
        request: Request,
        exc: EvidenceRequiredError,
    ) -> JSONResponse:
        del request
        return _error_response(
            status_code=422,
            code="evidence_required",
            message="draft_contains_unsupported_claim",
            fields={"missing_evidence": ",".join(exc.missing_fields)},
        )

    @application.get("/healthz")
    def health() -> dict[str, object]:
        return {"status": "ok", "mode": "fixture"}

    @application.get("/readyz")
    def readiness() -> dict[str, object]:
        repository = get_repository()
        seed_present = (
            repository.get_conversation(
                seeded_conversation_id,
                workspace_id=demo_workspace,
            )
            is not None
        )
        return {
            "status": "ready" if seed_present else "not_ready",
            "mode": "fixture",
            "fixture": {
                "workspace_id": demo_workspace,
                "seeded_conversation": seeded_conversation_id,
                "seed_present": seed_present,
            },
            "dependencies": {
                "database": "not_configured",
                "queue": "not_configured",
                "realtime": "not_configured",
                "provider": "fixture_only",
            },
        }

    @application.post("/api/v1/demo/reset")
    def reset_demo() -> dict[str, str]:
        repository = get_repository()
        result = repository.reset(build_freight_delay_event())
        return {
            "status": "reset",
            "mode": "fixture",
            "workspace_id": demo_workspace,
            "conversation_id": result.conversation_id,
        }

    @application.get("/api/v1/conversations")
    def list_conversations(
        workspace_id: str = "demo-workspace",
        status: str | None = None,
        queue: str | None = None,
        owner: str | None = None,
        priority: str | None = None,
        sla_state: str | None = None,
        channel: str | None = None,
    ) -> dict[str, object]:
        repository = get_repository()
        items = repository.list_conversations(
            workspace_id=workspace_id,
            status=status,
            queue=queue,
            owner=owner,
            priority=priority,
            sla_state=sla_state,
            channel=channel,
        )
        return {"items": items, "next_cursor": None}

    @application.get("/api/v1/conversations/{conversation_id}")
    def get_conversation(
        conversation_id: str,
        workspace_id: str = "demo-workspace",
    ) -> dict[str, object]:
        repository = get_repository()
        conversation = repository.get_conversation(
            conversation_id,
            workspace_id=workspace_id,
        )
        if conversation is None:
            raise HTTPException(status_code=404, detail="conversation_not_found")
        return conversation

    @application.post("/api/v1/conversations/{conversation_id}/ai/run")
    def run_ai(
        conversation_id: str,
        request: AiRunRequest,
        workspace_id: str | None = None,
    ) -> dict[str, object]:
        repository = get_repository()
        return repository.run_ai(
            conversation_id,
            action=request.action,
            workspace_id=workspace_id or request.workspace_id,
        )

    @application.post("/api/v1/conversations/{conversation_id}/assign")
    def assign_conversation(
        conversation_id: str,
        request: AssignmentRequest,
    ) -> dict[str, object]:
        repository = get_repository()
        return repository.assign_conversation(
            conversation_id,
            owner_id=request.owner_id,
            queue_id=request.queue_id,
            expected_version=request.expected_version,
            actor_id=request.actor_id,
            workspace_id=request.workspace_id,
        )

    @application.post("/api/v1/conversations/{conversation_id}/claim")
    def claim_conversation(
        conversation_id: str,
        request: ClaimRequest,
    ) -> dict[str, object]:
        repository = get_repository()
        return repository.claim_conversation(
            conversation_id,
            actor_id=request.actor_id,
            expected_version=request.expected_version,
            workspace_id=request.workspace_id,
        )

    @application.post("/api/v1/conversations/{conversation_id}/comments")
    def add_comment(
        conversation_id: str,
        request: CommentRequest,
    ) -> dict[str, object]:
        repository = get_repository()
        return repository.add_comment(
            conversation_id,
            body=request.body,
            actor_id=request.actor_id,
            client_request_id=request.client_request_id
            or f"comment-{uuid4()}",
            expected_version=request.expected_version,
            workspace_id=request.workspace_id,
        )

    @application.get("/api/v1/drafts/{draft_id}")
    def get_draft(
        draft_id: str,
        workspace_id: str = "demo-workspace",
    ) -> dict[str, object]:
        return get_repository().get_draft(draft_id, workspace_id=workspace_id)

    @application.patch("/api/v1/drafts/{draft_id}")
    def edit_draft(
        draft_id: str,
        request: DraftEditRequest,
    ) -> dict[str, object]:
        return get_repository().edit_draft(
            draft_id,
            body=request.body,
            expected_version=request.expected_version,
            actor_id=request.actor_id,
            workspace_id=request.workspace_id,
        )

    @application.post("/api/v1/drafts/{draft_id}/approve")
    def approve_draft(
        draft_id: str,
        request: DraftApprovalRequest,
    ) -> dict[str, object]:
        return get_repository().approve_draft(
            draft_id,
            expected_version=request.expected_version,
            actor_id=request.actor_id,
            workspace_id=request.workspace_id,
        )

    @application.post("/api/v1/drafts/{draft_id}/send")
    def send_draft(
        draft_id: str,
        request: DraftSendRequest,
    ) -> dict[str, object]:
        return get_repository().send_draft(
            draft_id,
            approval_id=request.approval_id,
            idempotency_key=request.idempotency_key,
            actor_id=request.actor_id,
            workspace_id=request.workspace_id,
        )

    @application.get("/api/v1/connectors")
    def list_connectors() -> dict[str, object]:
        return {"items": get_repository().list_connectors()}

    @application.post("/api/v1/connectors/{connector_id}/sync")
    def sync_connector(
        connector_id: str,
        request: SyncRequest,
    ) -> dict[str, object]:
        return get_repository().sync_connector(
            connector_id,
            kind=request.kind,
            idempotency_key=request.idempotency_key,
            failure_mode=request.failure_mode,
        )

    @application.post("/api/v1/connectors/{connector_id}/sync/{job_id}/retry")
    def retry_sync(
        connector_id: str,
        job_id: str,
    ) -> dict[str, object]:
        del connector_id
        return get_repository().retry_sync(job_id)

    @application.post("/api/v1/conversations/{conversation_id}/sla/start")
    def start_sla(
        conversation_id: str,
        request: SlaStartRequest,
    ) -> dict[str, object]:
        return get_repository().start_sla(
            conversation_id,
            expected_version=request.expected_version,
            actor_id=request.actor_id,
            workspace_id=request.workspace_id,
        )

    @application.post("/api/v1/conversations/{conversation_id}/sla/evaluate")
    def evaluate_sla(
        conversation_id: str,
        request: SlaEvaluateRequest,
    ) -> dict[str, object]:
        return get_repository().evaluate_sla(
            conversation_id,
            now=request.now,
            workspace_id=request.workspace_id,
        )

    @application.post("/api/v1/conversations/{conversation_id}/resolve")
    def resolve_conversation(
        conversation_id: str,
        request: ResolveRequest,
    ) -> dict[str, object]:
        return get_repository().resolve_conversation(
            conversation_id,
            expected_version=request.expected_version,
            actor_id=request.actor_id,
            workspace_id=request.workspace_id,
        )

    @application.get("/api/v1/events")
    def list_events(
        workspace_id: str = "demo-workspace",
        conversation_id: str | None = None,
        after_sequence: int = 0,
    ) -> dict[str, object]:
        return {
            "items": get_repository().list_events(
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                after_sequence=after_sequence,
            )
        }

    @application.get("/api/v1/rules")
    def list_rules() -> dict[str, object]:
        return {"items": get_repository().list_rules()}

    return application


demo_inbox = create_demo_inbox()
app = create_app()
