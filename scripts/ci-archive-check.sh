#!/usr/bin/env bash
set -euo pipefail

archive=${1:?usage: ci-archive-check.sh ARCHIVE}
root_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
expected_id=$(git -C "$root_dir" rev-parse --short HEAD)
test_root=$(mktemp -d)
trap 'rm -rf "$test_root"' EXIT
tar -tzf "$archive" > "$test_root/contents"
top_level=$(head -1 "$test_root/contents" | cut -d/ -f1)
test -n "$top_level"
test "$(grep -c "^$top_level/" "$test_root/contents")" -gt 5
tar -xzf "$archive" -C "$test_root"
package_root="$test_root/$top_level"
test -x "$package_root/install.sh"
test -f "$package_root/LICENSE"
test -f "$package_root/cdisplayagain.png"
test -f "$package_root/desktop-entry.template"
test -x "$package_root/bundle/cdisplayagain"

env_root="$test_root/env"
env HOME="$env_root/home" PREFIX="$env_root/prefix" XDG_DATA_HOME="$env_root/data" \
    "$package_root/install.sh"
env HOME="$env_root/home" PREFIX="$env_root/prefix" XDG_DATA_HOME="$env_root/data" \
    "$env_root/prefix/bin/cdisplayagain" --version | grep -F "build $expected_id)"
grep -F 'MimeType=' "$env_root/data/applications/cdisplayagain.desktop"
test -f "$env_root/data/icons/hicolor/256x256/apps/cdisplayagain.png"
env HOME="$env_root/home" PREFIX="$env_root/prefix" XDG_DATA_HOME="$env_root/data" \
    "$package_root/install.sh" --uninstall
test ! -e "$env_root/prefix/lib/cdisplayagain"
test ! -e "$env_root/prefix/bin/cdisplayagain"
test ! -e "$env_root/data/applications/cdisplayagain.desktop"
test ! -e "$env_root/data/icons/hicolor/256x256/apps/cdisplayagain.png"
echo "Archive contents and extracted installer checks passed"
