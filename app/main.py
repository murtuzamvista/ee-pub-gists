from contextlib import asynccontextmanager
from typing import Annotated, Any

import httpx2
import uvicorn
from fastapi import FastAPI, HTTPException, Path, Query, Request

from app.config import Settings

GITHUB_USERNAME_PATTERN = r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$"


def create_app(
    settings: Settings | None = None,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> FastAPI:
    configured_settings = settings or Settings.from_env()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "public-gists-api",
    }
    if configured_settings.github_token:
        headers["Authorization"] = f"Bearer {configured_settings.github_token}"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with httpx2.AsyncClient(
            timeout=configured_settings.request_timeout_seconds,
            headers=headers,
            transport=transport,
        ) as client:
            app.state.github_client = client
            yield

    app = FastAPI(title="Public GitHub Gists API", lifespan=lifespan)
    app.state.settings = configured_settings

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

        return gists

    return app


app = create_app()


if __name__ == "__main__":
    settings = app.state.settings
    uvicorn.run("app.main:app", host=settings.host, port=settings.port)
