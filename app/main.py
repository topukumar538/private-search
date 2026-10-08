import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.services.deduplication import remove_duplicates

from pathlib import Path
from fastapi.responses import FileResponse

from app.services.search import search_all

app = FastAPI(title="Private Search")

@app.middleware("http")
async def prevent_response_caching(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/", include_in_schema=False)
async def home():
    return FileResponse(STATIC_DIR / "index.html")

class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Search query cannot be empty.")

        return value


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/search")
async def search(body: SearchRequest):
    try:
        return await search_all(body.query)
    except RuntimeError:
        raise HTTPException(
            status_code=502,
            detail="Search sources are unavailable. Please try again.",
        ) from None