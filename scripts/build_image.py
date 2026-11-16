import subprocess
import sys
from pathlib import Path


def read_tool_versions() -> dict[str, str]:
    versions_file = Path(__file__).resolve().parents[1] / ".tool-versions"
    versions: dict[str, str] = {}

    try:
        lines = versions_file.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"Unable to read tool versions from {versions_file}: {exc}") from exc

    for line in lines:
        fields = line.split()
        if not fields or fields[0].startswith("#"):
            continue
        if len(fields) != 2 or fields[0] not in {"python", "uv"}:
            raise ValueError(f"Invalid tool version declaration: {line!r}")
        if fields[0] in versions:
            raise ValueError(f"Duplicate {fields[0]} version in {versions_file}")
        versions[fields[0]] = fields[1]

    missing = {"python", "uv"} - versions.keys()
    if missing:
        raise ValueError(f"Missing tool versions in {versions_file}: {', '.join(sorted(missing))}")

    return versions


def main() -> int:
    try:
        versions = read_tool_versions()
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    command = [
        "docker",
        "build",
        "--build-arg",
        f"PYTHON_VERSION={versions['python']}",
        "--build-arg",
        f"UV_VERSION={versions['uv']}",
        *sys.argv[1:],
    ]
    try:
        return subprocess.run(command, check=False).returncode
    except FileNotFoundError:
        print("Docker is required to build the image but was not found on PATH.", file=sys.stderr)
        return 127


if __name__ == "__main__":
    raise SystemExit(main())
