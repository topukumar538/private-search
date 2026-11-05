import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.services.cache import CACHE_CLEANUP_SECONDS
from app.services.http_client import create_http_client
from app.services.logging_config import configure_logging
from app.services.rate_limiter import RateLimiter, visitor_key
from app.services import search as search_module
from app.services.search import search_all

configure_logging()

STATIC_DIR = Path(__file__).resolve().parent / "static"

# Searches per visitor per minute, shared by every request. Memory only.
rate_limiter = RateLimiter()


async def clean_cache_forever():
    """Every few minutes, remove expired searches and finished
    rate-limit windows from memory, including ones nobody uses again."""
    while True:
        await asyncio.sleep(CACHE_CLEANUP_SECONDS)
        search_module.cache.remove_expired()
        rate_limiter.remove_expired()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One HTTP client for the app's whole life: created at startup,
    # closed at shutdown, shared by every search.
    async with create_http_client() as client:
        app.state.http_client = client
        cleaner = asyncio.create_task(clean_cache_forever())

        try:
            yield
        finally:
            cleaner.cancel()


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


def client_ip(request: Request) -> str:
    """The visitor's IP address.

    On Render, requests arrive through Render's proxy, which adds the real
    address at the END of X-Forwarded-For. A visitor can put fake addresses
    at the start of that header, so only the last one is trusted.
    """
    forwarded = request.headers.get("x-forwarded-for")

    if forwarded:
        return forwarded.split(",")[-1].strip()

    return request.client.host if request.client else "unknown"


@app.post("/api/search")
async def search(body: SearchRequest, request: Request):
    wait = rate_limiter.check(visitor_key(client_ip(request)))

    if wait:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many searches. Please wait a moment and try again."},
            headers={"Retry-After": str(wait)},
        )

    try:
        return await search_all(body.query, request.app.state.http_client)
    except RuntimeError:
        raise HTTPException(
            status_code=502,
            detail="Search sources are unavailable. Please try again.",
        ) from None