"""Generate build metadata consumed by packaged and source launches."""

from __future__ import annotations

import os
import subprocess
import tomllib
from pathlib import Path


def _git_output(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=False, capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def main() -> None:
    """Write the current project version and Git revision to build_info.py."""
    root = Path(__file__).resolve().parents[1]
    with (root / "pyproject.toml").open("rb") as pyproject:
        project = tomllib.load(pyproject)["project"]
    version = str(project["version"])
    revision = os.environ.get("CDISPLAYAGAIN_BUILD_ID") or _git_output(
        root, "rev-parse", "--short", "HEAD"
    )
    dirty = not os.environ.get("CDISPLAYAGAIN_BUILD_ID") and bool(
        _git_output(root, "status", "--porcelain")
    )
    build_id = f"{revision}-dirty" if dirty else revision
    (root / "build_info.py").write_text(
        f'BUILD_VERSION = {version!r}\nBUILD_ID = {build_id!r}\n', encoding="utf-8"
    )


if __name__ == "__main__":
    main()
