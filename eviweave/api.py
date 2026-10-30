"""Loopback API. Prompts, Answer, Judge and benchmark submissions are out of scope."""
from contextlib import asynccontextmanager
import hmac

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from adaptive_evidence.core import ConflictError
from . import __version__
from .runtime import Runtime, Settings


class Message(BaseModel):
    role: str = Field(min_length=1)
    content: str = Field(min_length=1)
    timestamp: int | None = Field(default=None, strict=True)


class AddRequest(BaseModel):
    user_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    messages: list[Message] = Field(min_length=1)


class SearchRequest(BaseModel):
    user_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    options: list[str] | None = None
    top_k: int = Field(default=100, ge=1, le=100, strict=True)


def create_app(settings=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        with Runtime(settings) as runtime:
            app.state.runtime = runtime
            yield

    app = FastAPI(title="EviWeave", version=__version__, lifespan=lifespan)

    def authenticate(authorization: str | None = Header(default=None)):
        if settings.api_token:
            expected = "Bearer " + settings.api_token
            if not authorization or not hmac.compare_digest(authorization.encode(), expected.encode()):
                raise HTTPException(401, "Invalid bearer token")

    @app.get("/health")
    def health():
        return dict(name="EviWeave", version=__version__, encoder=app.state.runtime.store.encoder.identity,
                    experimental=settings.experimental, baseline="exact32", generative_model_calls=0)

    @app.post("/add", dependencies=[Depends(authenticate)])
    async def add(request: AddRequest):
        try:
            count = app.state.runtime.store.add(user_id=request.user_id, request_id=request.request_id,
                                                session_id=request.session_id,
                                                messages=[m.model_dump() for m in request.messages])
            return dict(status="ok", added_chunks=count)
        except ConflictError as error:
            raise HTTPException(409, "Request ID already has a different payload") from error
        except ValueError as error:
            raise HTTPException(400, str(error)) from error

    @app.post("/search", dependencies=[Depends(authenticate)])
    async def search(request: SearchRequest):
        try:
            hits = app.state.runtime.store.search(user_id=request.user_id, query=request.query,
                                                   top_k=request.top_k, options=request.options,
                                                   mode="query_document_evidence")
            return dict(memories=hits)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error

    return app
