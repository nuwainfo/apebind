# Portable language runtimes

These examples wrap language runtimes distributed as Actually Portable Executables (APE) with APEBind's Node.js backend.

Each runtime directory contains a reviewed `*.apebind.yaml` semantic schema and a small `run.mjs` consumer. The generated npm package bundles the interpreter APE itself, so the consumer does not require that language runtime to be installed separately.

This is process-isolated embedding rather than an in-process FFI. The host talks to the bundled runtime through the executable boundary.

| Runtime | Package | Example | `--help` discovery |
|---|---|---|---|
| Janet | `janet-ape` | evaluate Janet source | manually reviewed schema; Janet uses `-h` rather than `--help` |
| Lua | `lua-ape` | evaluate Lua source | manually reviewed schema; Lua rejects `--help` |
| PHP | `php-ape` | evaluate PHP source | raw discovery included, then corrected by review |
| Python | `python-ape` | evaluate Python source | raw discovery included, then enriched by review |
| Tcl | `tcl-ape` | run a Tcl script file | manually authored; `tclsh --help` does not expose a CLI grammar |

The PHP raw discovery is intentionally kept next to the reviewed schema. PHP prints several alternative `Usage:` forms, which demonstrates why help discovery is only a bootstrap heuristic and why the reviewed schema is the real binding contract.

Generate any package with:

```bash
apebind generate examples/languages/<runtime>/<runtime>.apebind.yaml \
    --ape /path/to/<runtime-ape> \
    --lang node \
    -o generated/<runtime>-ape
```

The input APE may have any local filename. The reviewed schemas deliberately give the bundled package binaries `.com` filenames so the generated artifacts remain directly executable on Windows as well as POSIX systems.

After installing all five generated packages, `run-all.mjs` executes the same `6 * 7` computation in Janet, Lua, PHP, Python, and Tcl. Every runtime should print `42`.
