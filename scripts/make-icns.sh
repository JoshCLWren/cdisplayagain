#!/usr/bin/env bash
# Regenerate cdisplayagain.icns from cdisplayagain.png.
#
# The .icns is committed so cloners and CI build an identical bundle without
# needing macOS tooling; only re-run this when the source PNG changes.
set -euo pipefail

if [[ "$(uname)" != "Darwin" ]]; then
    echo "ERROR: iconutil is macOS only." >&2
    exit 1
fi

root_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source_png="$root_dir/cdisplayagain.png"
output_icns="$root_dir/cdisplayagain.icns"
iconset=$(mktemp -d)/cdisplayagain.iconset
trap 'rm -rf -- "$(dirname -- "$iconset")"' EXIT
mkdir -p -- "$iconset"

for size in 16 32 128 256 512; do
    sips -z "$size" "$size" "$source_png" --out "$iconset/icon_${size}x${size}.png" >/dev/null
    retina=$((size * 2))
    sips -z "$retina" "$retina" "$source_png" \
        --out "$iconset/icon_${size}x${size}@2x.png" >/dev/null
done

iconutil --convert icns --output "$output_icns" "$iconset"
echo "Wrote $output_icns"
