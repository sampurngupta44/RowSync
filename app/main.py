"""RowSync FastAPI application."""

from __future__ import annotations

import json
import queue
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from app.config import get_preview_row_limit, get_target_connections, is_valid_target
from app.database import connection
from app.schema import load_schema
from app.sync import preview_query, sync_query

app = FastAPI(title="RowSync", description="Copy MSSQL rows from production to target databases")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
schema_cache: dict[str, Any] = {}


class QueryRequest(BaseModel):
    sql: str = Field(..., min_length=1)


class ApplyRequest(BaseModel):
    sql: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)

    @field_validator("target")
    @classmethod
    def validate_target(cls, value: str) -> str:
        if not is_valid_target(value):
            available = ", ".join(get_target_connections()) or "(none configured)"
            raise ValueError(f"Unknown target '{value}'. Available targets: {available}")
        return value


@app.on_event("startup")
def load_production_schema() -> None:
    global schema_cache
    try:
        with connection("production") as conn:
            schema_cache = load_schema(conn)
    except Exception as exc:
        schema_cache = {"tables": [], "tableDetails": {}, "columnsByTable": {}, "error": str(exc)}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/targets")
def get_targets() -> dict[str, Any]:
    targets = get_target_connections()
    return {"targets": targets, "source": "production"}


@app.get("/api/schema")
def get_schema() -> dict[str, Any]:
    return schema_cache or {"tables": [], "tableDetails": {}, "columnsByTable": {}}


@app.post("/api/preview")
def preview(body: QueryRequest) -> dict[str, Any]:
    try:
        return preview_query(body.sql, get_preview_row_limit())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/apply")
def apply(body: ApplyRequest) -> StreamingResponse:
    event_queue: queue.Queue[tuple[str, dict[str, Any] | None] | None] = queue.Queue()

    def emit(message: str, data: dict[str, Any] | None = None) -> None:
        event_queue.put((message, data))

    def worker() -> None:
        try:
            sync_query(body.sql, body.target, emit)
        except Exception as exc:
            emit(f"Error: {exc}", {"error": str(exc)})
        finally:
            event_queue.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def event_stream():
        while True:
            item = event_queue.get()
            if item is None:
                yield "event: done\ndata: {}\n\n"
                break
            message, data = item
            payload = {"message": message}
            if data:
                payload.update(data)
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
