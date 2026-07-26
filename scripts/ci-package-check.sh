#!/usr/bin/env bash
set -euo pipefail

root_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
executable=${1:-"$root_dir/dist/cdisplayagain/cdisplayagain"}
expected_id=$(git -C "$root_dir" rev-parse --short HEAD)
version_output=$("$executable" --version)
if [[ "$version_output" != *"build $expected_id)"* ]]; then
    echo "ERROR: packaged build identity is wrong: $version_output" >&2
    exit 1
fi
echo "$version_output"

fixture_dir=$(mktemp -d)
test_root=$(mktemp -d)
trap 'rm -rf "$fixture_dir" "$test_root"' EXIT
fixture="$fixture_dir/smoke.cbz"
uv run python - "$fixture" <<'PY'
import io
import sys
import zipfile

from PIL import Image

image = Image.new("RGB", (320, 480), (32, 64, 96))
buffer = io.BytesIO()
image.save(buffer, format="PNG")
with zipfile.ZipFile(sys.argv[1], "w") as archive:
    archive.writestr("page_001.png", buffer.getvalue())
PY

echo "Starting packaged CBZ smoke test under Xvfb"
CDISPLAYAGAIN_LOG_DIR="$test_root/logs" xvfb-run -a "$executable" "$fixture" >"$test_root/smoke.log" 2>&1 &
smoke_pid=$!
sleep 1
if ! kill -0 "$smoke_pid" 2>/dev/null; then
    wait "$smoke_pid" || true
    cat "$test_root/smoke.log"
    echo "ERROR: packaged executable exited during startup smoke test." >&2
    exit 1
fi
for _ in {1..18}; do
    if grep -R -q "Opening comic: $fixture" "$test_root/logs" && \
        grep -R -q "cached page 0" "$test_root/logs"; then
        break
    fi
    sleep 0.5
done
if ! grep -R -q "Opening comic: $fixture" "$test_root/logs" || \
    ! grep -R -q "cached page 0" "$test_root/logs"; then
    cat "$test_root/smoke.log"
    find "$test_root/logs" -type f -maxdepth 2 -print -exec cat {} \;
    echo "ERROR: packaged smoke did not prove page 0 was rendered." >&2
    kill -TERM "$smoke_pid" 2>/dev/null || true
    wait "$smoke_pid" || true
    exit 1
fi
kill -INT "$smoke_pid" 2>/dev/null || true
for _ in {1..10}; do
    if ! kill -0 "$smoke_pid" 2>/dev/null; then break; fi
    sleep 0.5
done
if kill -0 "$smoke_pid" 2>/dev/null; then
    kill -TERM "$smoke_pid" 2>/dev/null || true
fi
wait "$smoke_pid" || true

installer="$root_dir/scripts/install-linux.sh"
installer_root="$test_root/installer"
mkdir -p "$installer_root"
cp -a "$root_dir/dist/cdisplayagain" "$installer_root/bundle"
cp "$root_dir/cdisplayagain.png" "$root_dir/scripts/desktop-entry.template" "$installer_root/"
cp "$installer" "$installer_root/install.sh"
chmod 0755 "$installer_root/install.sh"
env HOME="$test_root/home" PREFIX="$test_root/prefix" XDG_DATA_HOME="$test_root/data" \
    "$installer_root/install.sh"
env HOME="$test_root/home" PREFIX="$test_root/prefix" XDG_DATA_HOME="$test_root/data" \
    "$test_root/prefix/bin/cdisplayagain" --version | grep -F "build $expected_id)"
test -x "$test_root/prefix/bin/cdisplayagain"
test -f "$test_root/data/applications/cdisplayagain.desktop"
test -f "$test_root/data/icons/hicolor/256x256/apps/cdisplayagain.png"
env HOME="$test_root/home" PREFIX="$test_root/prefix" XDG_DATA_HOME="$test_root/data" \
    "$installer_root/install.sh" --uninstall
test ! -e "$test_root/prefix/lib/cdisplayagain"
test ! -e "$test_root/prefix/bin/cdisplayagain"
test ! -e "$test_root/data/applications/cdisplayagain.desktop"
test ! -e "$test_root/data/icons/hicolor/256x256/apps/cdisplayagain.png"
echo "Packaged smoke, temporary install, invocation, and uninstall checks passed"
