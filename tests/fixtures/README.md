# Test fixtures

`ape_fixture.c` is the executable fixture for the full test suite. It is compiled to `ape_fixture.com` with Cosmopolitan so inspection, generation, and generated-runtime tests exercise an actual APE.

With `cosmocc/` at the repository root:

```bash
python scripts/build_ape_fixture.py
pytest
```

Compiler discovery prefers `COSMOCC`, then `./cosmocc/bin/cosmocc`, then `PATH`.
