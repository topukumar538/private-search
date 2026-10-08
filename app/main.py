from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from app.services.http_client import create_http_client
from app.services.logging_config import configure_logging
from app.services.search import search_all

configure_logging()

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One HTTP client for the app's whole life: created at startup,
    # closed at shutdown, shared by every search.
    async with create_http_client() as client:
        app.state.http_client = client
        yield


app = FastAPI(title="Private Search", lifespan=lifespan)


@app.middleware("http")
async def prevent_response_caching(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Search query cannot be empty.")

        return value


@app.get("/", include_in_schema=False)
async def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/search")
async def search(body: SearchRequest, request: Request):
    try:
        return await search_all(body.query, request.app.state.http_client)
    except RuntimeError:
        raise HTTPException(
            status_code=502,
            detail="Search sources are unavailable. Please try again.",
        ) from None