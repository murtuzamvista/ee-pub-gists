import httpx2
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_settings(
    github_api_url: str = "https://api.github.test",
    github_token: str | None = None,
) -> Settings:
    return Settings(
        github_api_url=github_api_url,
        github_token=github_token,
        request_timeout_seconds=1,
        host="127.0.0.1",
        port=8080,
    )


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


def test_returns_not_found_when_github_user_does_not_exist() -> None:
    app = create_app(
        make_settings(),
        transport=httpx2.MockTransport(lambda request: httpx2.Response(404)),
    )
    with TestClient(app) as client:
        response = client.get("/unknown-user")

    assert response.status_code == 404
    assert response.json() == {"detail": "GitHub user not found"}


def test_returns_bad_gateway_for_upstream_errors_or_invalid_payloads() -> None:
    for upstream_response in (httpx2.Response(500), httpx2.Response(200, json={"message": "not a list"})):
        app = create_app(
            make_settings(),
            transport=httpx2.MockTransport(lambda request, result=upstream_response: result),
        )
        with TestClient(app) as client:
            response = client.get("/octocat")
        assert response.status_code == 502


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
        ("/bad/name", 404),
        ("/ends-with-", 422),
        (f"/{'a' * 40}", 422),
    ],
)
def test_rejects_invalid_usernames(path: str, expected_status: int) -> None:
    app = create_app(make_settings(), transport=httpx2.MockTransport(lambda request: httpx2.Response(200, json=[])))
    with TestClient(app) as client:
        response = client.get(path)

    assert response.status_code == expected_status
