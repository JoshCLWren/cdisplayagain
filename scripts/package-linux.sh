#!/usr/bin/env bash
set -euo pipefail

root_dir=$(CDISPLAYAGAIN_PACKAGE_ROOT=1; cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
bundle_dir="$root_dir/dist/cdisplayagain"
executable="$bundle_dir/cdisplayagain"

if [[ ! -x "$executable" ]]; then
    echo "ERROR: expected completed onedir build at $executable" >&2
    echo "Run 'make build-onedir' first." >&2
    exit 1
fi

if [[ -n "$(git -C "$root_dir" status --porcelain --untracked-files=all)" ]]; then
    echo "ERROR: refusing to package a dirty worktree." >&2
    git -C "$root_dir" status --short >&2
    exit 1
fi

readarray -t project_values < <(python - "$root_dir/pyproject.toml" <<'PY'
import sys
import tomllib

with open(sys.argv[1], "rb") as file:
    project = tomllib.load(file)["project"]
print(project["version"])
PY
)
version=${project_values[0]}
revision=$(git -C "$root_dir" rev-parse --short HEAD)
asset_name="cdisplayagain-${version}-linux-x86_64.tar.gz"
staging_root=$(mktemp -d)
trap 'rm -rf "$staging_root"' EXIT
package_root="$staging_root/cdisplayagain-${version}-linux-x86_64"
mkdir -p "$package_root/bundle"
cp -a "$bundle_dir/." "$package_root/bundle/"
install -m 0644 "$root_dir/cdisplayagain.png" "$package_root/cdisplayagain.png"
install -m 0644 "$root_dir/LICENSE" "$package_root/LICENSE"
install -m 0755 "$root_dir/scripts/install-linux.sh" "$package_root/install.sh"
install -m 0644 "$root_dir/scripts/desktop-entry.template" "$package_root/desktop-entry.template"
cat > "$package_root/README-install.txt" <<EOF
cdisplayagain ${version} for Linux x86-64

Build: ${revision}

Install for the current user with:
  ./install.sh

The installer needs no sudo and places the application under ~/.local by
default. It accepts HOME, PREFIX, and XDG_DATA_HOME overrides. To remove it:
  ./install.sh --uninstall

This archive contains a PyInstaller onedir bundle and does not require Python.
EOF

output_path="$root_dir/$asset_name"
commit_epoch=$(git -C "$root_dir" show -s --format=%ct HEAD)
tar -C "$staging_root" --sort=name --mtime="@$commit_epoch" --owner=0 --group=0 --numeric-owner \
    -czf "$output_path" "cdisplayagain-${version}-linux-x86_64"
printf '%s\n' "$output_path"
