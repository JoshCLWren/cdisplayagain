#!/usr/bin/env bash
set -euo pipefail

root_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
build_id=$(git -C "$root_dir" rev-parse --short HEAD)
docker run --rm \
    -e "CDISPLAYAGAIN_BUILD_ID=$build_id" \
    -v "$root_dir:/workspace" \
    -w /workspace \
    ubuntu:22.04 \
    bash -euxo pipefail -c '
        apt-get update -qq
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
            ca-certificates curl git libglib2.0-0 libglib2.0-dev libexpat1-dev \
            libvips-dev python3-tk python3-venv unar
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH=/root/.local/bin:$PATH
        export UV_PROJECT_ENVIRONMENT=/tmp/cdisplayagain-venv
        uv python install 3.13
        uv sync --locked
        uv run python scripts/generate_build_info.py
        uv run pyinstaller --clean --noconfirm cdisplayagain.spec
    '
