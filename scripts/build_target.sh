#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$root/build"

cc=${CC:-clang}
if [ "${SANITIZERS:-default}" = "none" ]; then
    sanitizers=
else
    sanitizers=${SANITIZERS:--fsanitize=address,undefined}
fi
common_flags="-std=c89 -Wall -Wextra -Wpedantic -Wno-newline-eof -fno-omit-frame-pointer"

exec "$cc" $common_flags -Wno-deprecated-declarations $sanitizers -I"$root/vendor/cjson" \
    "$root/vendor/cjson/cJSON.c" "$root/harness/cjson_harness.c" \
    -o "$root/build/cjson_harness"