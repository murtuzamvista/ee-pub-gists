import math
import os
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    github_api_url: str
    github_token: str | None
    request_timeout_seconds: float
    cache_ttl_seconds: float
    cache_max_entries: int
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
            cache_ttl_seconds = float(os.getenv("CACHE_TTL_SECONDS", "60"))
            port = int(os.getenv("PORT", "8080"))
            cache_max_entries = int(os.getenv("CACHE_MAX_ENTRIES", "1000"))
        except ValueError as exc:
            raise ValueError(
                "REQUEST_TIMEOUT_SECONDS, CACHE_TTL_SECONDS, PORT, and CACHE_MAX_ENTRIES must be numeric"
            ) from exc

        if not math.isfinite(request_timeout_seconds) or request_timeout_seconds <= 0:
            raise ValueError("REQUEST_TIMEOUT_SECONDS must be a positive finite number")
        if not math.isfinite(cache_ttl_seconds) or cache_ttl_seconds < 0:
            raise ValueError("CACHE_TTL_SECONDS must be a non-negative finite number")
        if cache_max_entries < 1:
            raise ValueError("CACHE_MAX_ENTRIES must be a positive integer")
        if not 1 <= port <= 65535:
            raise ValueError("PORT must be between 1 and 65535")

        host = os.getenv("HOST", "0.0.0.0")
        if not host:
            raise ValueError("HOST must not be empty")

        return cls(
            github_api_url=github_api_url,
            github_token=os.getenv("GITHUB_TOKEN") or None,
            request_timeout_seconds=request_timeout_seconds,
            cache_ttl_seconds=cache_ttl_seconds,
            cache_max_entries=cache_max_entries,
            host=host,
            port=port,
        )
