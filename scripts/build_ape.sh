#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

set -euo pipefail

SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIRECTORY/.." && pwd)"
APE_DIRECTORY="${APEBIND_APE_DIRECTORY:-$PROJECT_ROOT/ape}"
PYTHON_APE="$APE_DIRECTORY/python.com"
COSMOFY_APE="$APE_DIRECTORY/cosmofy.com"
OUTPUT_APE="$APE_DIRECTORY/apebind.com"
HOST_PYTHON="${PYTHON:-python}"
BUILD_DIRECTORY="$(mktemp -d "${TMPDIR:-/tmp}/apebind-ape.XXXXXX")"
HTTP_PORT=""
HTTP_SERVER_PID=""

cleanup() {
    if [ -n "$HTTP_SERVER_PID" ] && kill -0 "$HTTP_SERVER_PID" 2>/dev/null; then
        kill "$HTTP_SERVER_PID" 2>/dev/null || true
        wait "$HTTP_SERVER_PID" 2>/dev/null || true
    fi

    rm -rf "$BUILD_DIRECTORY"
}

find_free_port() {
    "$HOST_PYTHON" - <<'PY'
import socket

with socket.socket() as socket_handle:
    socket_handle.bind(('127.0.0.1', 0))
    print(socket_handle.getsockname()[1])
PY
}

ensure_python_ape() {
    if [ -f "$PYTHON_APE" ]; then
        return
    fi

    local source_ape="$PROJECT_ROOT/cosmocc/python312.com"
    if [ ! -f "$source_ape" ]; then
        echo "Missing Python APE: $source_ape" >&2
        exit 1
    fi

    mkdir -p "$APE_DIRECTORY"
    cp "$source_ape" "$PYTHON_APE"
    chmod +x "$PYTHON_APE"
}

start_python_server() {
    HTTP_PORT="$(find_free_port)"
    (
        cd "$APE_DIRECTORY"
        "$PYTHON_APE" -m http.server --bind 127.0.0.1 "$HTTP_PORT"
    ) >"$BUILD_DIRECTORY/python-http.log" 2>&1 &
    HTTP_SERVER_PID=$!

    for _attempt in $(seq 1 20); do
        if curl -fsS "http://127.0.0.1:$HTTP_PORT/python.com" >/dev/null; then
            return
        fi

        if ! kill -0 "$HTTP_SERVER_PID" 2>/dev/null; then
            cat "$BUILD_DIRECTORY/python-http.log" >&2
            exit 1
        fi

        sleep 0.1
    done

    echo 'Timed out while starting the temporary Python APE HTTP server.' >&2
    exit 1
}

trap cleanup EXIT

ensure_python_ape

if [ ! -f "$COSMOFY_APE" ]; then
    echo "Missing cosmofy APE: $COSMOFY_APE" >&2
    echo 'Place cosmofy.com in the ape directory before building.' >&2
    exit 1
fi

chmod +x "$COSMOFY_APE"
rm -f "$OUTPUT_APE"

"$HOST_PYTHON" "$SCRIPT_DIRECTORY/prepare_ape_lib.py" \
    --output "$BUILD_DIRECTORY/Lib" \
    --entry "$BUILD_DIRECTORY/APEBind.py"

"$PYTHON_APE" -m compileall --invalidation-mode=unchecked-hash -b -q "$BUILD_DIRECTORY/Lib"
find "$BUILD_DIRECTORY/Lib" -type f -name '*.py' -delete
find "$BUILD_DIRECTORY/Lib" -type d -name '__pycache__' -exec rm -rf {} +

start_python_server

(
    cd "$BUILD_DIRECTORY"
    "$COSMOFY_APE" \
        --python-url "http://127.0.0.1:$HTTP_PORT/python.com" \
        APEBind.py \
        -o apebind.com

    zip -qr apebind.com Lib
)

mv "$BUILD_DIRECTORY/apebind.com" "$OUTPUT_APE"
chmod +x "$OUTPUT_APE"
"$OUTPUT_APE" --version

echo "Built APEBind APE: $OUTPUT_APE"
