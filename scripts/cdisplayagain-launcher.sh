#!/usr/bin/env sh

launch_ns=$(date +%s%N)
export CDISPLAYAGAIN_LAUNCH_NS="$launch_ns"

exec "$(dirname "$0")/cdisplayagain" "$@"
