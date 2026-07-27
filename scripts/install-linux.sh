#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 [--uninstall]"
}

if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--uninstall" ) ]]; then
    usage >&2
    exit 2
fi
if [[ -z "${HOME:-}" ]]; then
    echo "ERROR: HOME must be set." >&2
    exit 1
fi

prefix=${PREFIX:-"$HOME/.local"}
data_home=${XDG_DATA_HOME:-"$prefix/share"}
install_root="$prefix/lib/cdisplayagain"
bin_path="$prefix/bin/cdisplayagain"
desktop_path="$data_home/applications/cdisplayagain.desktop"
icon_path="$data_home/icons/hicolor/256x256/apps/cdisplayagain.png"
manifest_path="$install_root/.install-manifest"
mime_types=(
    application/x-cbz application/x-cbr application/vnd.comicbook+zip
    application/vnd.comicbook-rar application/x-ext-cbz application/x-ext-cbr
)
source_root=$(CDISPLAYAGAIN_INSTALL_ROOT=1; cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

remove_mime_entry() {
    local mime=$1
    local mimeapps
    local temp_file
    for mimeapps in "${XDG_CONFIG_HOME:-$HOME/.config}/mimeapps.list" \
        "$data_home/applications/mimeapps.list"; do
        if [[ -f "$mimeapps" ]]; then
            temp_file=$(mktemp)
            awk -F= -v mime="$mime" '$1 != mime { print }' "$mimeapps" > "$temp_file"
            chmod --reference="$mimeapps" "$temp_file"
            mv -- "$temp_file" "$mimeapps"
        fi
    done
}

restore_mime_defaults() {
    local mime previous current
    if [[ ! -f "$manifest_path" ]]; then
        return
    fi
    while IFS=$'\t' read -r mime previous; do
        current=$(xdg-mime query default "$mime" 2>/dev/null || true)
        if [[ "$current" == "cdisplayagain.desktop" ]]; then
            if [[ -n "$previous" ]]; then
                xdg-mime default "$previous" "$mime" 2>/dev/null || true
            else
                remove_mime_entry "$mime"
            fi
        fi
    done < "$manifest_path"
}

remove_installation() {
    rm -rf -- "$install_root"
    rm -rf -- "$install_root"
    rm -f -- "$bin_path" "$desktop_path" "$icon_path"
    rmdir --ignore-fail-on-non-empty "$prefix/bin" "$prefix/lib" \
        "$data_home/applications" "$data_home/icons/hicolor/256x256/apps" \
        "$data_home/icons/hicolor/256x256" "$data_home/icons/hicolor" "$data_home/icons" \
        2>/dev/null || true
    echo "Removed cdisplayagain from $prefix"
}

if [[ $# -eq 1 ]]; then
    if command -v xdg-mime >/dev/null 2>&1; then
        restore_mime_defaults
    fi
    remove_installation
    exit 0
fi

if [[ ! -x "$source_root/bundle/cdisplayagain" ]]; then
    echo "ERROR: the release bundle is incomplete." >&2
    exit 1
fi
mkdir -p -- "$install_root" "$prefix/bin" "$(dirname -- "$desktop_path")" \
    "$(dirname -- "$icon_path")"
manifest_tmp=$(mktemp)
trap 'rm -f -- "$manifest_tmp"' EXIT
if [[ -f "$manifest_path" ]]; then
    cp -- "$manifest_path" "$manifest_tmp"
elif command -v xdg-mime >/dev/null 2>&1; then
    for mime in "${mime_types[@]}"; do
        printf '%s\t%s\n' "$mime" "$(xdg-mime query default "$mime" 2>/dev/null || true)" \
            >> "$manifest_tmp"
    done
else
    : > "$manifest_tmp"
fi
rm -rf -- "$install_root"
mkdir -p -- "$install_root"
cp -a -- "$source_root/bundle/." "$install_root/"
install -m 0644 "$manifest_tmp" "$manifest_path"
cat > "$bin_path" <<EOF
#!/usr/bin/env sh
exec "$install_root/cdisplayagain" "\$@"
EOF
chmod 0755 "$bin_path"
install -m 0644 "$source_root/cdisplayagain.png" "$icon_path"
sed -e "s|@EXEC@|$bin_path|g" -e "s|@ICON@|cdisplayagain|g" \
    "$source_root/desktop-entry.template" > "$desktop_path"

if command -v xdg-mime >/dev/null 2>&1; then
    for mime in "${mime_types[@]}"; do
        xdg-mime default cdisplayagain.desktop "$mime" 2>/dev/null || true
    done
else
    echo "Note: xdg-mime is unavailable; MIME associations were not registered."
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$(dirname -- "$desktop_path")" >/dev/null 2>&1 || true
else
    echo "Note: update-desktop-database is unavailable; the desktop menu may refresh later."
fi
echo "Installed cdisplayagain in $install_root"
echo "Run '$bin_path --version' to verify it."
echo "Uninstall with '$source_root/install.sh --uninstall' (using the same overrides)."
