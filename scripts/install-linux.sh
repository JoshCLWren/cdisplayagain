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
source_root=$(CDISPLAYAGAIN_INSTALL_ROOT=1; cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

remove_installation() {
    rm -rf -- "$install_root"
    rm -f -- "$bin_path" "$desktop_path" "$icon_path"
    rmdir --ignore-fail-on-non-empty "$prefix/bin" "$prefix/lib" \
        "$data_home/applications" "$data_home/icons/hicolor/256x256/apps" \
        "$data_home/icons/hicolor/256x256" "$data_home/icons/hicolor" "$data_home/icons" \
        2>/dev/null || true
    echo "Removed cdisplayagain from $prefix"
}

if [[ $# -eq 1 ]]; then
    remove_installation
    exit 0
fi

if [[ ! -x "$source_root/bundle/cdisplayagain" ]]; then
    echo "ERROR: the release bundle is incomplete." >&2
    exit 1
fi
mkdir -p -- "$install_root" "$prefix/bin" "$(dirname -- "$desktop_path")" \
    "$(dirname -- "$icon_path")"
rm -rf -- "$install_root"
mkdir -p -- "$install_root"
cp -a -- "$source_root/bundle/." "$install_root/"
cat > "$bin_path" <<EOF
#!/usr/bin/env sh
exec "$install_root/cdisplayagain" "\$@"
EOF
chmod 0755 "$bin_path"
install -m 0644 "$source_root/cdisplayagain.png" "$icon_path"
sed -e "s|@EXEC@|$bin_path|g" -e "s|@ICON@|cdisplayagain|g" \
    "$source_root/desktop-entry.template" > "$desktop_path"

if command -v xdg-mime >/dev/null 2>&1; then
    for mime in application/x-cbz application/x-cbr application/vnd.comicbook+zip \
        application/vnd.comicbook-rar application/x-ext-cbz application/x-ext-cbr; do
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
