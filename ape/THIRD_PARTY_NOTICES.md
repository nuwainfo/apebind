# Third-Party Notices for APE Tools

This directory ships the prebuilt APE toolchain required to run and rebuild
`apebind.com` without a separate download.

## `cosmofy.com`

`cosmofy.com` is Cosmofy 0.1.0, the Cosmopolitan Python bundler, from
Metaist LLC. It is licensed under MIT; see `LICENSES/COSMOFY-MIT.txt`.

## `python.com` and `apebind.com`

`python.com` is the Cosmopolitan CPython 3.12.3 APE used by Cosmofy.
`apebind.com` embeds that runtime. The complete CPython license extracted
from the bundled runtime is in `LICENSES/CPYTHON-3.12.txt`.

The runtime uses Cosmopolitan Libc. Cosmopolitan's project license is ISC;
see `LICENSES/COSMOPOLITAN-ISC.txt`. Cosmopolitan also embeds applicable
component notices in its APE binaries.

The supplied Python APE was built using the `ahgamut/superconfigure` build
recipes. Superconfigure is released under the Unlicense; see
`LICENSES/SUPERCONFIGURE-UNLICENSE.txt`. This notice records provenance even
where the build-recipe source is not itself embedded in the final binary.

## APEBind

APEBind is MIT licensed; see the repository-root `LICENSE`. Its bundled
pure-Python runtime dependencies retain their upstream distribution metadata
inside `apebind.com` when supplied by the active build environment.
