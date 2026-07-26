#!/usr/bin/env bash
set -euo pipefail

family=${1:?usage: compatibility-test.sh apt|dnf|zypper}
workspace=${WORKSPACE:-/workspace}
artifact_dir="$workspace/artifact"
archive=$(find "$artifact_dir" -maxdepth 1 -type f -name '*.tar.gz' -print -quit)
checksum="$artifact_dir/SHA256SUMS"
test -n "$archive"
test -f "$checksum"

case "$family" in
    apt)
        apt-get update -qq
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
            bash ca-certificates coreutils gzip tar xvfb \
            libexpat1 libfontconfig1 libglib2.0-0 libx11-6 libxext6 libxi6 \
            libxrender1 libxss1 libxtst6
        ;;
    dnf)
        dnf install -y \
            bash ca-certificates coreutils gzip tar xorg-x11-server-Xvfb \
            expat fontconfig glib2 libX11 libXext libXi libXrender \
            libXss libXtst
        ;;
    zypper)
        zypper --non-interactive refresh
        zypper --non-interactive install --no-recommends \
            bash ca-certificates coreutils gzip tar xorg-x11-server \
            libexpat1 fontconfig glib2 libX11-6 libXext6 libXi6 \
            libXrender1 libXss1 libXtst6
        ;;
    *)
        echo "Unknown package family: $family" >&2
        exit 2
        ;;
esac

cd "$artifact_dir"
sha256sum -c "$checksum"
tar -tzf "$archive" > "$artifact_dir/archive.contents"
test -s "$artifact_dir/archive.contents"
extract_root=$(cut -d/ -f1 "$artifact_dir/archive.contents" | head -1)
tar -xzf "$archive"
package_root="$artifact_dir/$extract_root"
test -x "$package_root/install.sh"
test -x "$package_root/bundle/cdisplayagain"

temp_root=$(mktemp -d)
trap 'rm -rf "$temp_root"' EXIT
env HOME="$temp_root/home" PREFIX="$temp_root/prefix" XDG_DATA_HOME="$temp_root/data" \
    "$package_root/install.sh"
wrapper="$temp_root/prefix/bin/cdisplayagain"
export LD_LIBRARY_PATH="$temp_root/prefix/lib/cdisplayagain/_internal:$temp_root/prefix/lib/cdisplayagain/_internal/pillow.libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
version_output=$(env HOME="$temp_root/home" PREFIX="$temp_root/prefix" \
    XDG_DATA_HOME="$temp_root/data" "$wrapper" --version)
build_sha=${BUILD_SHA:?}
grep -F "build ${build_sha:0:7})" <<<"$version_output"

for native_file in "$temp_root/prefix/lib/cdisplayagain/cdisplayagain" \
    $(find "$temp_root/prefix/lib/cdisplayagain" -type f -name '*.so*'); do
    if ldd "$native_file" 2>&1 | tee -a "$workspace/ldd.log" | grep -q 'not found'; then
        echo "Unresolved dependency in $native_file" >&2
        exit 1
    fi
done

run_smoke() {
    local input=$1
    xvfb-run -a "$wrapper" "$input" >"$workspace/$(basename "$input").log" 2>&1 &
    local smoke_pid=$!
    sleep 3
    if ! kill -0 "$smoke_pid" 2>/dev/null; then
        wait "$smoke_pid" || true
        cat "$workspace/$(basename "$input").log"
        return 1
    fi
    kill -TERM "$smoke_pid"
    wait "$smoke_pid" || true
}

run_smoke "$workspace/tests/fixtures/test_cbz.cbz"
run_smoke "$workspace/tests/fixtures/test_cbr.cbr"
env HOME="$temp_root/home" PREFIX="$temp_root/prefix" XDG_DATA_HOME="$temp_root/data" \
    "$package_root/install.sh" --uninstall
test ! -e "$temp_root/prefix/lib/cdisplayagain"
test ! -e "$temp_root/prefix/bin/cdisplayagain"
test ! -e "$temp_root/data/applications/cdisplayagain.desktop"
test ! -e "$temp_root/data/icons/hicolor/256x256/apps/cdisplayagain.png"
echo "Compatibility checks passed for $family"
