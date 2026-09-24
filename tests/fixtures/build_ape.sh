#!/usr/bin/env sh
set -eu
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
exec python "$PROJECT_ROOT/scripts/build_ape_fixture.py" "$@"
