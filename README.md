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

Install [uv](https://docs.astral.sh/uv/), then sync the project and test
dependencies:

```sh
uv sync --extra test
uv run python -m app.main
```

The project requires Python 3.11 or newer; uv can manage the interpreter if
needed.
The service listens on `http://localhost:8080`. Try
`curl 'http://localhost:8080/octocat'`.

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

### Build and run the container

The image uses Python 3.14 on Alpine Linux 3.23 and a pinned `uv` 0.13.7
builder image.

```sh
docker build -t public-gists-api .
docker run --rm -p 8080:8080 public-gists-api
```

To pass an optional GitHub token without adding it to the image:

```sh
docker run --rm -p 8080:8080 -e GITHUB_TOKEN="$GITHUB_TOKEN" public-gists-api
```
