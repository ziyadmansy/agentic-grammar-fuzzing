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
common_flags="-std=c99 -Wall -Wextra -fno-omit-frame-pointer"

exec "$cc" $common_flags $sanitizers -I"$root/vendor/parson" \
    "$root/vendor/parson/parson.c" "$root/harness/parson_harness.c" \
    -o "$root/build/parson_harness"
