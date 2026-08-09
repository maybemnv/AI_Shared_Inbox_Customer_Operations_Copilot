from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.fixture import create_demo_inbox


app = FastAPI(
    title="AI Shared Inbox Customer Operations Copilot",
    version="0.1.0-fixture",
    description="Fixture-first local Phase 1 surface; no live provider or queue is configured.",
)
demo_inbox = create_demo_inbox()


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    del request
    code = "not_found" if exc.status_code == 404 else "internal_error"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": code,
            "message": str(exc.detail),
            "requestId": str(uuid4()),
            "retryable": False,
        },
    )


@app.get("/healthz")
def health() -> dict[str, object]:
    return {"status": "ok", "mode": "fixture"}


@app.get("/readyz")
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


@app.get("/api/v1/conversations")
def list_conversations(
    workspace_id: str = "demo-workspace",
    status: str | None = None,
    queue: str | None = None,
    owner: str | None = None,
    priority: str | None = None,
    sla_state: str | None = None,
    channel: str | None = None,
) -> dict[str, object]:
    items = demo_inbox.list_conversations(
        workspace_id=workspace_id,
        status=status,
        queue=queue,
        owner=owner,
        priority=priority,
        sla_state=sla_state,
        channel=channel,
    )
    return {"items": items, "next_cursor": None}


@app.get("/api/v1/conversations/{conversation_id}")
def get_conversation(conversation_id: str) -> dict[str, object]:
    conversation = demo_inbox.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    return conversation
