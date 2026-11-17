import httpx2
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_settings(
    github_api_url: str = "https://api.github.test",
    github_token: str | None = None,
    cache_ttl_seconds: float = 60,
    cache_max_entries: int = 1000,
) -> Settings:
    return Settings(
        github_api_url=github_api_url,
        github_token=github_token,
        request_timeout_seconds=1,
        cache_ttl_seconds=cache_ttl_seconds,
        cache_max_entries=cache_max_entries,
        host="127.0.0.1",
        port=8080,
    )


# Health checks report application lifecycle state without contacting GitHub.
def test_health_checks_do_not_call_github() -> None:
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, json=[])

    app = create_app(make_settings(), transport=httpx2.MockTransport(handler))
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200

    assert requests == []


# Verifies the returned Gists and the username, pagination, and API-version sent to GitHub.
def test_returns_gists_and_forwards_pagination() -> None:
    gist_list = [{"id": "abc123", "description": "A public gist"}]
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, json=gist_list)

    app = create_app(make_settings(), transport=httpx2.MockTransport(handler))
    with TestClient(app) as client:
        response = client.get("/octocat?page=2&per_page=50")

    assert response.status_code == 200
    assert response.json() == gist_list
    assert str(requests[0].url) == "https://api.github.test/users/octocat/gists?page=2&per_page=50"
    assert requests[0].headers["X-GitHub-Api-Version"] == "2022-11-28"


# Repeated requests for one page use the cache; a different page gets its own upstream response.
def test_caches_gists_by_username_and_pagination() -> None:
    request_count = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal request_count
        request_count += 1
        return httpx2.Response(200, json=[{"id": str(request_count)}])

    app = create_app(make_settings(), transport=httpx2.MockTransport(handler))
    with TestClient(app) as client:
        first = client.get("/octocat")
        second = client.get("/octocat")
        another_page = client.get("/octocat?page=2")

    assert first.json() == [{"id": "1"}]
    assert second.json() == first.json()
    assert another_page.json() == [{"id": "2"}]
    assert request_count == 2


# Confirms a response is fetched again once its configured cache TTL has elapsed.
def test_expired_cache_entry_is_refetched(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [0.0]
    monkeypatch.setattr("app.main.monotonic", lambda: clock[0])
    request_count = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal request_count
        request_count += 1
        return httpx2.Response(200, json=[{"id": str(request_count)}])

    app = create_app(make_settings(cache_ttl_seconds=5), transport=httpx2.MockTransport(handler))
    with TestClient(app) as client:
        first = client.get("/octocat")
        clock[0] = 5.0
        after_expiry = client.get("/octocat")

    assert first.json() == [{"id": "1"}]
    assert after_expiry.json() == [{"id": "2"}]
    assert request_count == 2


# Ensures a zero TTL makes every identical request reach GitHub.
def test_zero_cache_ttl_disables_caching() -> None:
    request_count = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal request_count
        request_count += 1
        return httpx2.Response(200, json=[])

    app = create_app(make_settings(cache_ttl_seconds=0), transport=httpx2.MockTransport(handler))
    with TestClient(app) as client:
        client.get("/octocat")
        client.get("/octocat")

    assert request_count == 2


# Confirms adding entries beyond the configured limit evicts old entries.
def test_cache_is_bounded_by_max_entries() -> None:
    request_count = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal request_count
        request_count += 1
        return httpx2.Response(200, json=[])

    app = create_app(
        make_settings(cache_max_entries=1),
        transport=httpx2.MockTransport(handler),
    )
    with TestClient(app) as client:
        client.get("/octocat")
        client.get("/another-user")
        client.get("/octocat")

    assert request_count == 3


# Ensures an upstream failure is not cached and a later request can succeed.
def test_does_not_cache_upstream_errors() -> None:
    request_count = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal request_count
        request_count += 1
        status_code = 502 if request_count == 1 else 200
        return httpx2.Response(status_code, json=[])

    app = create_app(make_settings(), transport=httpx2.MockTransport(handler))
    with TestClient(app) as client:
        first = client.get("/octocat")
        second = client.get("/octocat")

    assert first.status_code == 502
    assert second.status_code == 200
    assert request_count == 2


# Verifies a configured GitHub token is sent as a bearer authorization header.
def test_uses_optional_github_token() -> None:
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, json=[])

    app = create_app(make_settings(github_token="test-token"), transport=httpx2.MockTransport(handler))
    with TestClient(app) as client:
        response = client.get("/octocat")

    assert response.status_code == 200
    assert requests[0].headers["Authorization"] == "Bearer test-token"


# Maps GitHub's 404 response to the API's user-not-found response.
def test_returns_not_found_when_github_user_does_not_exist() -> None:
    app = create_app(
        make_settings(),
        transport=httpx2.MockTransport(lambda request: httpx2.Response(404)),
    )
    with TestClient(app) as client:
        response = client.get("/unknown-user")

    assert response.status_code == 404
    assert response.json() == {"detail": "GitHub user not found"}


# Maps GitHub server failures and malformed successful payloads to 502 responses.
def test_returns_bad_gateway_for_upstream_errors_or_invalid_payloads() -> None:
    for upstream_response in (httpx2.Response(500), httpx2.Response(200, json={"message": "not a list"})):
        app = create_app(
            make_settings(),
            transport=httpx2.MockTransport(lambda request, result=upstream_response: result),
        )
        with TestClient(app) as client:
            response = client.get("/octocat")
        assert response.status_code == 502


# Maps a timed-out GitHub request to a 504 response.
def test_returns_gateway_timeout_when_github_request_times_out() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("upstream timed out", request=request)

    app = create_app(make_settings(), transport=httpx2.MockTransport(handler))
    with TestClient(app) as client:
        response = client.get("/octocat")

    assert response.status_code == 504


@pytest.mark.parametrize(
    ("path", "expected_status"),
    [
        # A nested path does not match the single-segment username route.
        ("/bad/name", 404),
        # Usernames cannot end with a hyphen or exceed GitHub's 39-character limit.
        ("/ends-with-", 422),
        (f"/{'a' * 40}", 422),
    ],
)
# Checks that malformed usernames are rejected before reaching GitHub.
def test_rejects_invalid_usernames(path: str, expected_status: int) -> None:
    app = create_app(make_settings(), transport=httpx2.MockTransport(lambda request: httpx2.Response(200, json=[])))
    with TestClient(app) as client:
        response = client.get(path)

    assert response.status_code == expected_status
