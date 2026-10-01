#!/usr/bin/env bash
# SPDX-License-Identifier: MIT

set -euo pipefail

SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIRECTORY/.." && pwd)"
DIST_DIRECTORY="${APEBIND_DIST_DIRECTORY:-$PROJECT_ROOT/dist}"
OUTPUT_APE="$DIST_DIRECTORY/apebind.com"
HOST_PYTHON="${PYTHON:-python}"
BUILD_DIRECTORY="$(mktemp -d "${TMPDIR:-/tmp}/apebind-ape.XXXXXX")"
PYTHON_APE="$BUILD_DIRECTORY/python.com"
COSMOFY_APE="$BUILD_DIRECTORY/pythoncosmofy.com"
HTTP_PORT=""
HTTP_SERVER_PID=""

PYTHON_APE_REPOSITORY='bear0330/python-ape'
PYTHON_APE_ASSET='python.com'
COSMOFY_REPOSITORY='bear0330/pythoncosmofy'
COSMOFY_ASSET='pythoncosmofy.com'

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

download_latest_release_asset() {
    local repository="$1"
    local asset_name="$2"
    local destination="$3"

    echo "Fetching latest '$asset_name' release asset from $repository..."
    "$HOST_PYTHON" - "$repository" "$asset_name" "$destination" <<'PY'
import json
import sys
import urllib.request

repository, asset_name, destination = sys.argv[1:4]
headers = {
    'Accept': 'application/vnd.github+json',
    'User-Agent': 'apebind-build-ape',
}

request = urllib.request.Request(
    f'https://api.github.com/repos/{repository}/releases/latest',
    headers=headers,
)
with urllib.request.urlopen(request) as response:
    release = json.load(response)

asset = next(
    (item for item in release.get('assets', []) if item.get('name') == asset_name),
    None,
)
if asset is None:
    raise SystemExit(
        f"Release {release.get('tag_name')} of {repository} has no asset named "
        f'{asset_name!r}'
    )

download_request = urllib.request.Request(
    asset['browser_download_url'],
    headers={'User-Agent': 'apebind-build-ape'},
)
with urllib.request.urlopen(download_request) as response, open(destination, 'wb') as handle:
    handle.write(response.read())
PY
    chmod +x "$destination"
}

start_python_server() {
    HTTP_PORT="$(find_free_port)"
    (
        cd "$BUILD_DIRECTORY"
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

mkdir -p "$DIST_DIRECTORY"

download_latest_release_asset "$PYTHON_APE_REPOSITORY" "$PYTHON_APE_ASSET" "$PYTHON_APE"
download_latest_release_asset "$COSMOFY_REPOSITORY" "$COSMOFY_ASSET" "$COSMOFY_APE"

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
