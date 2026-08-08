#!/usr/bin/env bash
set -euo pipefail

root_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
app_bundle="$root_dir/dist/cdisplayagain.app"

if [[ "$(uname)" != "Darwin" ]]; then
    echo "ERROR: macOS packaging must run on macOS." >&2
    exit 1
fi
if [[ ! -x "$app_bundle/Contents/MacOS/cdisplayagain" ]]; then
    echo "ERROR: expected a completed app bundle at $app_bundle" >&2
    echo "Run 'make build' first." >&2
    exit 1
fi
if [[ -n "$(git -C "$root_dir" status --porcelain --untracked-files=all)" ]]; then
    echo "ERROR: refusing to package a dirty worktree." >&2
    git -C "$root_dir" status --short >&2
    exit 1
fi

version=$(uv run --no-project python - "$root_dir/pyproject.toml" <<'PY'
import sys
import tomllib

with open(sys.argv[1], "rb") as file:
    print(tomllib.load(file)["project"]["version"])
PY
)
arch=$(uname -m)
asset_name="cdisplayagain-${version}-macos-${arch}.zip"
staging_root=$(mktemp -d)
trap 'rm -rf "$staging_root"' EXIT
package_root="$staging_root/cdisplayagain-${version}-macos-${arch}"
mkdir -p "$package_root"

# ditto preserves the bundle's ad-hoc signature and extended attributes; zip does not.
ditto "$app_bundle" "$package_root/cdisplayagain.app"
install -m 0644 "$root_dir/LICENSE" "$package_root/LICENSE"
install -m 0755 "$root_dir/scripts/install-macos.sh" "$package_root/install.sh"
cat > "$package_root/README-install.txt" <<EOF
cdisplayagain ${version} for macOS ${arch}

Build: $(git -C "$root_dir" rev-parse --short HEAD)

Install with:
  ./install.sh

This copies cdisplayagain.app to /Applications, registers it with Launch
Services, and makes it the default handler for .cbz/.cbr/.cbt/.cba when the
'duti' helper is available (brew install duti). Override the destination with
MACOS_APPDIR, e.g. MACOS_APPDIR=~/Applications ./install.sh. Remove it with:
  ./install.sh --uninstall

The bundle is unsigned and un-notarized. macOS quarantines apps downloaded from
a browser, so on first launch use right-click > Open, or clear the flag with:
  xattr -dr com.apple.quarantine /Applications/cdisplayagain.app

This archive bundles its own Python, Tk, Pillow, libvips, and unrar runtimes.
EOF

output_path="$root_dir/$asset_name"
rm -f "$output_path"
ditto -c -k --sequesterRsrc --keepParent "$package_root" "$output_path"
printf '%s\n' "$output_path"
