import math
import os
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    github_api_url: str
    github_token: str | None
    request_timeout_seconds: float
    host: str
    port: int

    @classmethod
    def from_env(cls) -> "Settings":
        github_api_url = os.getenv("GITHUB_API_URL", "https://api.github.com").rstrip("/")
        parsed_url = urlsplit(github_api_url)
        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.hostname
            or parsed_url.username
            or parsed_url.password
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ValueError("GITHUB_API_URL must be an HTTP(S) URL without credentials, query, or fragment")

        try:
            request_timeout_seconds = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "5"))
            port = int(os.getenv("PORT", "8080"))
        except ValueError as exc:
            raise ValueError("REQUEST_TIMEOUT_SECONDS and PORT must be numeric") from exc

        if not math.isfinite(request_timeout_seconds) or request_timeout_seconds <= 0:
            raise ValueError("REQUEST_TIMEOUT_SECONDS must be a positive finite number")
        if not 1 <= port <= 65535:
            raise ValueError("PORT must be between 1 and 65535")

        host = os.getenv("HOST", "0.0.0.0")
        if not host:
            raise ValueError("HOST must not be empty")

        return cls(
            github_api_url=github_api_url,
            github_token=os.getenv("GITHUB_TOKEN") or None,
            request_timeout_seconds=request_timeout_seconds,
            host=host,
            port=port,
        )
