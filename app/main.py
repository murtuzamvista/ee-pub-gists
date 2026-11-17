from collections import OrderedDict
from contextlib import asynccontextmanager
from time import monotonic
from typing import Annotated, Any

import httpx2
import uvicorn
from fastapi import FastAPI, HTTPException, Path, Query, Request, Response

from app.config import Settings

GITHUB_USERNAME_PATTERN = r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$"
GistCache = OrderedDict[tuple[str, int, int], tuple[float, list[dict[str, Any]]]]


def create_app(
    settings: Settings | None = None,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> FastAPI:
    configured_settings = settings or Settings.from_env()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ee-pub-gists",
    }
    if configured_settings.github_token:
        headers["Authorization"] = f"Bearer {configured_settings.github_token}"

    # Create one shared GitHub client at startup and close it automatically at shutdown.
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with httpx2.AsyncClient(
            timeout=configured_settings.request_timeout_seconds,
            headers=headers,
            transport=transport,
        ) as client:
            # Store the client so request handlers can reuse its connection pool.
            app.state.github_client = client
            yield

    app = FastAPI(title="Public GitHub Gists API", lifespan=lifespan)
    app.state.settings = configured_settings
    app.state.gists_cache = GistCache()

    @app.get("/health/live", include_in_schema=False)
    async def liveness() -> Response:
        return Response(status_code=200)

    @app.get("/health/ready", include_in_schema=False)
    async def readiness(request: Request) -> Response:
        github_client: httpx2.AsyncClient | None = getattr(request.app.state, "github_client", None)
        if github_client is None or github_client.is_closed:
            return Response(status_code=503)
        return Response(status_code=200)

    @app.get("/{username}", response_model=list[dict[str, Any]])
    async def get_public_gists(
        request: Request,
        username: Annotated[
            str,
            Path(min_length=1, max_length=39, pattern=GITHUB_USERNAME_PATTERN),
        ],
        page: Annotated[int, Query(ge=1)] = 1,
        per_page: Annotated[int, Query(ge=1, le=100)] = 30,
    ) -> list[dict[str, Any]]:
        cache_key = (username, page, per_page)
        cache: GistCache = request.app.state.gists_cache
        if configured_settings.cache_ttl_seconds > 0:
            cached_entry = cache.get(cache_key)
            if cached_entry is not None:
                expires_at, cached_gists = cached_entry
                if expires_at > monotonic():
                    # Mark this entry recently used so the least-recently-used entry is evicted first.
                    cache.move_to_end(cache_key)
                    return cached_gists
                # Discard expired data before fetching a fresh response.
                del cache[cache_key]

        url = f"{configured_settings.github_api_url}/users/{username}/gists"
        try:
            response = await request.app.state.github_client.get(
                url,
                params={"page": page, "per_page": per_page},
            )
        except httpx2.TimeoutException as exc:
            raise HTTPException(status_code=504, detail="GitHub API request timed out") from exc
        except httpx2.RequestError as exc:
            raise HTTPException(status_code=502, detail="Unable to reach GitHub API") from exc

        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="GitHub user not found")
        if not response.is_success:
            raise HTTPException(status_code=502, detail="GitHub API returned an error")

        try:
            gists = response.json()
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="GitHub API returned invalid JSON") from exc
        if not isinstance(gists, list) or not all(isinstance(gist, dict) for gist in gists):
            raise HTTPException(status_code=502, detail="GitHub API returned an invalid Gists response")

        if configured_settings.cache_ttl_seconds > 0:
            cache[cache_key] = (monotonic() + configured_settings.cache_ttl_seconds, gists)
            # Keep new entries at the recent end; overflow eviction removes from the opposite end.
            cache.move_to_end(cache_key)
            while len(cache) > configured_settings.cache_max_entries:
                cache.popitem(last=False)

        return gists

    return app


app = create_app()


if __name__ == "__main__":
    settings = app.state.settings
    uvicorn.run("app.main:app", host=settings.host, port=settings.port)
