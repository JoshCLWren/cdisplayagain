#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 [--uninstall]"
}

if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--uninstall" ) ]]; then
    usage >&2
    exit 2
fi
if [[ "$(uname)" != "Darwin" ]]; then
    echo "ERROR: this installer is macOS only; use scripts/install-linux.sh on Linux." >&2
    exit 1
fi

app_name="cdisplayagain.app"
bundle_id="io.github.joshclwren.cdisplayagain"
app_dir=${MACOS_APPDIR:-/Applications}
installed_app="$app_dir/$app_name"
prefix=${PREFIX:-"$HOME/.local"}
bin_path="$prefix/bin/cdisplayagain"
extensions=(cbz cbr cbt cba)
lsregister=/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister
source_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

# With no explicit destination, sweep both standard locations so an earlier
# install cannot leave a second copy behind for Finder to prefer. An explicit
# MACOS_APPDIR stays scoped to itself: callers pointing this at a scratch
# directory must never have their real install removed underneath them.
if [[ -n "${MACOS_APPDIR:-}" ]]; then
    install_locations=("$installed_app")
else
    install_locations=("/Applications/$app_name" "$HOME/Applications/$app_name")
fi

register_with_launch_services() {
    if [[ -x "$lsregister" ]]; then
        "$lsregister" -f "$installed_app" >/dev/null 2>&1 || true
    fi
}

remove_existing_installs() {
    local removed=0 location
    for location in "${install_locations[@]}"; do
        [[ -d "$location" ]] || continue
        if [[ -x "$lsregister" ]]; then
            "$lsregister" -u "$location" >/dev/null 2>&1 || true
        fi
        if ! rm -rf -- "$location" 2>/dev/null; then
            # Only the destination has to be removable; a leftover elsewhere
            # (say /Applications when installing to ~/Applications without
            # admin rights) is worth a warning, not a failed install.
            if [[ "$location" == "$installed_app" ]]; then
                echo "ERROR: could not remove the existing install at $location." >&2
                echo "Remove it manually, or re-run with sudo." >&2
                exit 1
            fi
            echo "WARNING: could not remove an older install at $location" >&2
            continue
        fi
        echo "Removed previous install at $location"
        removed=1
    done
    rm -f -- "$bin_path"
    return $((removed == 0))
}

warn_about_stray_copies() {
    command -v mdfind >/dev/null 2>&1 || return 0
    local stray
    while IFS= read -r stray; do
        [[ -n "$stray" ]] || continue
        # The build output and any release archive are expected; only flag copies
        # somewhere Finder might launch instead of the one just installed.
        [[ "$stray" == "$installed_app" || "$stray" == "$source_root"/* ]] && continue
        echo "Note: another copy is registered at $stray"
        echo "      Delete it if Finder opens the wrong one."
    done < <(mdfind "kMDItemCFBundleIdentifier == '$bundle_id'" 2>/dev/null)
}

if [[ $# -eq 1 ]]; then
    if remove_existing_installs; then
        echo "Uninstalled cdisplayagain."
    else
        echo "Nothing to uninstall."
    fi
    exit 0
fi

# Support both a repo checkout (dist/) and an extracted release archive.
for candidate in "$source_root/dist/$app_name" "$source_root/$app_name"; do
    if [[ -d "$candidate" ]]; then
        built_app=$candidate
        break
    fi
done
if [[ -z "${built_app:-}" ]]; then
    echo "ERROR: no $app_name found. Run 'make build' first." >&2
    exit 1
fi
if [[ ! -x "$built_app/Contents/MacOS/cdisplayagain" ]]; then
    echo "ERROR: $built_app is incomplete; rebuild with 'make build'." >&2
    exit 1
fi

mkdir -p -- "$app_dir" 2>/dev/null || true
if [[ ! -w "$app_dir" ]]; then
    echo "ERROR: $app_dir is not writable." >&2
    echo "Retry with 'sudo $0' or install elsewhere: MACOS_APPDIR=~/Applications $0" >&2
    exit 1
fi

remove_existing_installs || true

mkdir -p -- "$app_dir" "$prefix/bin"
cp -a -- "$built_app" "$installed_app"

# Copying rewrites nothing, but an unsigned bundle that moved needs its ad-hoc
# signature refreshed or arm64 refuses to exec it.
if command -v codesign >/dev/null 2>&1; then
    codesign --force --sign - --timestamp=none "$installed_app" >/dev/null 2>&1 || true
fi

cat > "$bin_path" <<EOF
#!/usr/bin/env sh
exec "$installed_app/Contents/MacOS/cdisplayagain" "\$@"
EOF
chmod 0755 "$bin_path"

register_with_launch_services

if [[ -n "${MACOS_APPDIR:-}" ]]; then
    # Claiming the system-wide default for a copy in a scratch or non-standard
    # directory would leave Finder pointing at something the caller may delete.
    echo "Note: MACOS_APPDIR is set, so system default handlers were left alone."
elif command -v duti >/dev/null 2>&1; then
    for extension in "${extensions[@]}"; do
        duti -s "$bundle_id" "$extension" all 2>/dev/null || true
    done
    echo "Set cdisplayagain as the default handler for: ${extensions[*]}"
else
    echo "Note: 'duti' is not installed, so the default handler was not forced."
    echo "      Install it with 'brew install duti' and re-run, or set it manually:"
    echo "      right-click a .cbz > Get Info > Open With > cdisplayagain > Change All."
fi

warn_about_stray_copies

echo "Installed $installed_app"
echo "Run '$bin_path --version' to verify it."
echo "Uninstall with '$0 --uninstall'."
