## :warning: Please read these instructions carefully and entirely first
* Clone this repository to your local machine.
* Use your IDE of choice to complete the assignment.
* When you have completed the assignment, you need to  push your code to this repository and [mark the assignment as completed by clicking here](https://app.snapcode.review/submission_links/4bd8f6ba-243b-4ffe-b146-1d48600931db).
* Once you mark it as completed, your access to this repository will be revoked. Please make sure that you have completed the assignment and pushed all code from your local machine to this repository before you click the link.

## Operability Take-Home Exercise

Welcome to the start of our recruitment process for Operability Engineers. It was great to speak to you regarding an opportunity to join the Equal Experts network!

Please write code to deliver a solution to the problems outlined below.

We appreciate that your time is valuable and do not expect this exercise to **take more than 90 minutes**. If you think this exercise will take longer than that, I **strongly** encourage you to please get in touch to ask any clarifying questions.

### Submission guidelines
**Do**
- Provide a README file in text or markdown format that documents a concise way to set up and run the provided solution.
- Take the time to read any applicable API or service docs, it may save you significant effort.
- Make your solution simple and clear. We aren't looking for overly complex ways to solve the problem since in our experience, simple and clear solutions to problems are generally the most maintainable and extensible solutions.

**Don't**

Expect the reviewer to dedicate a machine to review the test by:

- Installing software globally that may conflict with system software
- Requiring changes to system-wide configurations
- Providing overly complex solutions that need to spin up a ton of unneeded supporting dependencies. We aspire to keep our dev experiences as simple as possible (but no simpler)!
- Include identifying information in your submission. We are endeavouring to make our review process anonymous to reduce bias.

### Exercise
If you have any questions on the below exercise, please do get in touch and we’ll answer as soon as possible.

#### Build an API, test it, and package it into a container
- Build a simple HTTP web server API in any general-purpose programming language[^1] that interacts with the GitHub API and responds to requests on `/<USER>` with a list of the user’s publicly available Gists[^2].
- Create an automated test to validate that your web server API works. An example user to use as test data is `octocat`.
- Package the web server API into a docker container that listens for requests on port `8080`. You do not need to publish the resulting container image in any container registry, but we are expecting the Dockerfile in the submission.
- The solution may optionally provide other functionality (e.g. pagination, caching) but the above **must** be implemented.

Best of luck,
Equal Experts
__________________________________________
[^1]: For example Go, Python or Ruby but not Bash or Powershell.
[^2]: https://docs.github.com/en/rest/gists/gists?apiVersion=2022-11-28

## Solution

This FastAPI service returns public Gists from GitHub for a username:

```http
GET /<username>
```

It forwards optional `page` and `per_page` query parameters to GitHub (`page`
defaults to `1`; `per_page` defaults to `30` and is limited to `100`). A missing
GitHub user returns `404`; GitHub connectivity, upstream, or response-format
errors return a gateway error.

Successful Gists responses are cached in memory for 60 seconds by default,
separately for each username and pagination combination. The cache is bounded
to 1,000 entries per application process and is cleared when the process
restarts. Set `CACHE_TTL_SECONDS=0` to disable caching.

### Run locally

Install [uv](https://docs.astral.sh/uv/), then sync the project, test, and
development dependencies:

```sh
uv sync --locked --extra test --group dev
uv run pre-commit install
uv run python -m app.main
```

The project requires Python 3.11 or newer; uv can manage the interpreter if
needed.
The service listens on `http://localhost:8080`. Try
`curl 'http://localhost:8080/octocat'`.

The pre-commit hooks require Go to build and run Gitleaks. They scan staged
changes for leaked secrets, check Python syntax and debug statements, validate
YAML/JSON/TOML, check for merge-conflict markers and whitespace issues, and
run the test suite. To run all checks manually across the repository:

```sh
uv run pre-commit run --all-files
```

Configuration is supplied through environment variables; no `.env` file is
required:

| Variable | Default | Description |
|---|---|---|
| `GITHUB_API_URL` | `https://api.github.com` | GitHub API base URL |
| `GITHUB_TOKEN` | unset | Optional token for authenticated API rate limits |
| `REQUEST_TIMEOUT_SECONDS` | `5` | Timeout for a GitHub API request |
| `CACHE_TTL_SECONDS` | `60` | Cache lifetime in seconds; `0` disables caching |
| `CACHE_MAX_ENTRIES` | `1000` | Maximum number of cached responses per process |
| `HOST` | `0.0.0.0` | Address on which the service listens |
| `PORT` | `8080` | Listening port |

### Run tests

```sh
uv run pytest
```

Tests use a mocked GitHub API and do not require network access or credentials.

### Continuous integration

The dedicated dev pipeline runs secret scanning, tests, and dependency audits
on pushes to `develop`, then builds the image once, scans it with Trivy, and
publishes it to Docker Hub only if no HIGH or CRITICAL vulnerabilities are
found. It then updates `overlays/dev/kustomization.yaml` in the
`murtuzamvista/ee-pub-gists-gitops` repository to the immutable-by-convention
`sha-<commit>` tag. QA and production promotion will be handled by separate
workflows.

The former CI and release workflow is manual-only (`workflow_dispatch`) while
the new pipelines are introduced. It no longer runs automatically on pushes,
pull requests, or release-tag creation; its old release-tag publishing steps
are inactive until a dedicated release workflow is added.

Configure the repository secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`
with credentials that can publish to `murtaza1983/ee-pub-gists`. Configure
Docker Hub to prevent overwriting `sha-*` and `v*` tags so both candidate and
release references remain immutable; GitHub Actions uses these names but cannot
enforce registry tag immutability itself.

Configure the `GITOPS_TOKEN` Actions secret with a fine-grained token (or GitHub
App token) that has **Contents: read and write** access to the
`murtuzamvista/ee-pub-gists-gitops` repository. The dev pipeline uses this
credential only after the image has passed CI and vulnerability scanning.
Python and uv versions are defined once in `.tool-versions` and used by CI and
the Docker build.

### Build and run the container

The image uses the Python and uv versions defined in `.tool-versions`, with
Alpine Linux 3.23. A multi-stage build keeps uv and build-time files out of the
runtime image, and the runtime installs only Uvicorn's core dependencies.

```sh
uv run python scripts/build_image.py -t ee-pub-gists .
docker run --rm -p 8080:8080 ee-pub-gists
```

To pass an optional GitHub token without adding it to the image:

```sh
docker run --rm -p 8080:8080 -e GITHUB_TOKEN="$GITHUB_TOKEN" ee-pub-gists
```
