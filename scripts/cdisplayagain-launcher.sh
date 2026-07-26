#!/usr/bin/env sh

launch_ns=$(date +%s%N)
export CDISPLAYAGAIN_LAUNCH_NS="$launch_ns"

runtime_dir=${XDG_RUNTIME_DIR:-/tmp}
socket_path="$runtime_dir/cdisplayagain-$(id -u).sock"
ipc_client="$(dirname "$0")/cdisplayagain-ipc.py"
if [ -S "$socket_path" ] && [ "$#" -gt 0 ]; then
    if [ -f "$ipc_client" ] && python3 "$ipc_client" "$socket_path" "$1"; then
        exit 0
    fi
fi

exec "$(dirname "$0")/cdisplayagain" "$@"
