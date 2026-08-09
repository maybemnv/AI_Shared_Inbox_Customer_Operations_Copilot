from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.fixture import create_demo_inbox
from app.ingestion import (
    ConversationNotFoundError,
    InMemoryInbox,
    VersionConflictError,
)


class AiRunRequest(BaseModel):
    action: Literal["classify", "classify_and_route", "route"]


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

    def get_repository() -> InMemoryInbox:
        if fixed_repository is not None:
            return fixed_repository
        return demo_inbox

    application = FastAPI(
        title="AI Shared Inbox Customer Operations Copilot",
        version="0.2.0-fixture",
        description="Fixture-first local surface; no live provider or queue is configured.",
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

    @application.get("/healthz")
    def health() -> dict[str, object]:
        return {"status": "ok", "mode": "fixture"}

    @application.get("/readyz")
    def readiness() -> dict[str, object]:
        return {
            "status": "ready",
            "mode": "fixture",
            "dependencies": {
                "database": "not_configured",
                "queue": "not_configured",
                "realtime": "not_configured",
                "provider": "fixture_only",
            },
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
        conversation = repository.get_conversation(conversation_id)
        if conversation is None or conversation["workspace_id"] != workspace_id:
            raise HTTPException(status_code=404, detail="conversation_not_found")
        return conversation

    @application.post("/api/v1/conversations/{conversation_id}/ai/run")
    def run_ai(
        conversation_id: str,
        request: AiRunRequest,
        workspace_id: str = "demo-workspace",
    ) -> dict[str, object]:
        repository = get_repository()
        return repository.run_ai(
            conversation_id,
            action=request.action,
            workspace_id=workspace_id,
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
