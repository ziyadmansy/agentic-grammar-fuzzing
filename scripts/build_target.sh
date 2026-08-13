#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$root/build"

if [ -n "${CC:-}" ]; then
    cc=$CC
elif [ "$(uname -s)" = "Darwin" ] && [ -x /opt/homebrew/opt/llvm/bin/clang ]; then
    # Apple's clang/ASan (Xcode 17, macOS 26) deadlocks in AsanInitFromRtl()
    # during shadow-memory setup; Homebrew's clang does not.
    cc=/opt/homebrew/opt/llvm/bin/clang
else
    cc=clang
fi
if [ "${SANITIZERS:-default}" = "none" ]; then
    sanitizers=
else
    sanitizers=${SANITIZERS:--fsanitize=address,undefined}
fi
common_flags="-std=c89 -Wall -Wextra -Wpedantic -Wno-newline-eof -fno-omit-frame-pointer"

exec "$cc" $common_flags -Wno-deprecated-declarations $sanitizers -I"$root/vendor/cjson" \
    "$root/vendor/cjson/cJSON.c" "$root/harness/cjson_harness.c" \
    -o "$root/build/cjson_harness"