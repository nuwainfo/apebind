# APEBind — Turn Actual Portable Executable CLI executables into self-contained, language-native packages

APEBind treats an [Actually Portable Executable (APE)](https://github.com/jart/cosmopolitan)'s command-line surface as an **executable ABI**. It recursively inspects `--help`, produces a human-editable neutral schema, and generates a language package that bundles the same APE and invokes it through a subprocess boundary.

Install a generated package through its native package manager, then use the bundled CLI through an API that follows the target language's conventions. One APE and one reviewed CLI schema can produce independently distributed Python, Node.js, and Java packages.

## Repository layout

The development scripts expect the Cosmopolitan toolchain to live next to the APEBind source directories, matching this layout:

```text
apebind/
├── cosmocc/
│   ├── bin/
│   │   └── cosmocc
│   ├── include/
│   ├── lib/
│   └── ...
├── scripts/
├── src/
├── tests/
├── docs/
├── examples/
├── pyproject.toml
└── README.md
```

`cosmocc/` is ignored by Git and is not included in APEBind release archives. You can also set `COSMOCC=/path/to/cosmocc` if the compiler lives elsewhere.

## Bootstrap

For a new checkout with `cosmocc/` in the layout above:

```bash
python scripts/bootstrap.py
```

Bootstrap performs the complete development setup:

1. creates `.venv` if necessary;
2. installs APEBind and development dependencies;
3. builds `tests/fixtures/ape_fixture.com` using `cosmocc`;
4. runs the full pytest suite, including the real APE integration test;
5. builds the APEBind sdist and wheel into `dist/` using the bootstrapped environment.

Useful variants:

```bash
python scripts/bootstrap.py --skip-ape-fixture
python scripts/bootstrap.py --skip-tests
python scripts/bootstrap.py --skip-build
python scripts/bootstrap.py --venv /path/to/venv
```

Individual repository tasks are also available:

```bash
python scripts/build_ape_fixture.py
python scripts/test.py --build-ape-fixture
python scripts/build.py
python scripts/clean.py
```

## Build APEBind as an APE

`scripts/build_ape.sh` packages APEBind itself as a self-contained
`ape/apebind.com`. The repository includes the required `ape/python.com` and
`ape/cosmofy.com`, so a checkout can run the prebuilt APE immediately. The
same directory holds the generated `Lib/` tree and license notices for the
bundled tools.

Run the script from a POSIX shell with an active Python environment that has
APEBind's runtime dependencies installed. `PYTHON` selects that interpreter
and defaults to `python`:

```bash
PYTHON=python3 bash scripts/build_ape.sh
./ape/apebind.com --help
```

The build copies APEBind, Click, Jinja2, PyYAML, attrs, cattrs, and their
portable Python dependencies into `Lib/`; it deliberately omits platform
extension modules before compiling the tree with the bundled Python APE.

## APEBind can bind itself, which is mostly useless and very fun

`ape/apebind.com` is itself an APE CLI. That means it is also a perfectly valid
input to APEBind. No special self-hosting path is required: APEBind can inspect
its own help, emit a normal schema for itself, and generate a language binding
that bundles another copy of `apebind.com`.

```bash
./ape/apebind.com inspect ./ape/apebind.com -o apebind-self.apebind.yaml
./ape/apebind.com validate apebind-self.apebind.yaml
./ape/apebind.com generate \
    apebind-self.apebind.yaml \
    --ape ./ape/apebind.com \
    --lang python \
    -o ./generated/apebind
```

The amusing part is that the generated binding exposes APEBind's own typed
`generate()` operation. The bundled `apebind.com` can therefore generate the
next binding generation:

```python
import apebind

result = apebind.generate(
    'apebind-self.apebind.yaml',
    ape='./ape/apebind.com',
    lang='python',
    output='./generated/apebind-generation-two',
)

assert result.return_code == 0
```

And that second binding contains `apebind.com` again, so the loop can continue:

```text
apebind.com
    -> generated APEBind binding
        -> bundled apebind.com
            -> another generated APEBind binding
                -> bundled apebind.com
                    -> ...
```

This has almost no practical value. It is just a fun consequence of the design:
APEBind treats executable CLI structure as its input ABI, and APEBind happens to
be an executable CLI too. The repository has an integration test for this so the
trick remains real rather than becoming a README-only claim.

This is **self-application**, not full compiler self-hosting. Building
`ape/apebind.com` still relies on the bundled Python APE and `cosmofy.com`; the
interesting property here is that once `apebind.com` exists, APEBind's ordinary
inspect/schema/generate pipeline can be applied to itself repeatedly.

## What v0.4.1 includes

- APE v0.1 header detection.
- Recursive `--help` discovery for nested command trees.
- Explicit hidden-command seeds via repeated `--command` or a YAML `--command-file`.
- Conservative parsing for common argparse, Click/clap, and Cobra-style help layouts.
- Named primary-command sections can be promoted into real command/operation nodes when the usage path and section agree.
- Strict YAML or JSON schema loading/dumping.
- CLI grammar and public library operations modeled separately.
- Python, Node.js, and Java package generation with the same APE bundled as package data.
- Generated runtime with no dependency on APEBind.
- One-shot execution with command/text/JSON/JSON-file results.
- Persistent process sessions with JSON-file readiness, stdout iteration, stop/wait/cleanup, and non-zero-exit exceptions.
- Runtime-owned JSONL event channels with event discrimination, field projection, listener replay, history, and lifecycle error propagation.
- Raw argv escape hatch for commands/flags not yet represented in the schema.
- POSIX launch through `/bin/sh` for shebang-less APE compatibility; Windows launches the APE directly.
- Generated Python wheel, Node npm pack/install/run, and Java JAR compile/run coverage in the test suite.

## Real-world use

A real project built with APEBind is [ffl-python](https://github.com/nuwainfo/ffl-python). It packages an APE application behind a normal Python API while keeping the executable bundled with the package.

That project is useful as a real-world reference, but it is not part of APEBind's design vocabulary. APEBind itself only understands executable grammar, lifecycle, results, events, and language projection. The examples below therefore use the repository fixture or other neutral APEs.

## Demo case

[LangZoo.js](https://github.com/bear0330/lang-zoo-js) is a deliberately playful APEBind demo. It uses the Node.js backend to package several portable language runtimes as independently installable npm packages, then runs the same small computation in each one. It demonstrates the generator and distribution model; it is not a production reference application.

## Typical workflow

The repository includes `tests/fixtures/ape_fixture.com`, a small APE CLI used by the test suite. Build it first when necessary:

```bash
python scripts/build_ape_fixture.py
```

### 1. Inspect an APE

```bash
apebind inspect ./tests/fixtures/ape_fixture.com \
    -o ./generated/fixture.apebind.yaml
```

APEBind starts at the root help surface and recursively follows subcommands that the CLI actually describes. The fixture exposes commands such as `echo`, `math`, `serve`, and `json`, including nested math operations.

A CLI may also have valid commands that its root help does not enumerate. Those names cannot be inferred safely, so they must be supplied explicitly:

```bash
apebind inspect ./tool.com \
    -o ./generated/tool.apebind.yaml \
    --command repair \
    --command "admin reset"
```

For a larger hidden-command inventory, use `--command-file` instead. Explicit seeds still participate in recursive discovery, so a seeded command can expose additional children through its own help.

`--help` parsing is a bootstrap heuristic, not a trusted ABI. Review the generated schema before code generation. `examples/fixture.apebind.yaml` is the repository's small, neutral example of a reviewed schema.

### 2. Edit semantic operations

CLI syntax and library semantics are separate. The fixture's `serve` command is a useful example: the CLI only exposes flags, while the schema can state that the process is persistent and that readiness is reported through a runtime-owned JSON file.

```yaml
operations:
  - name: serve
    command: [serve]
    execution: persistent
    result:
      format: json_file
      option_flag: --json
      field: link
      ready_timeout_seconds: 5
      strip: true
```

Because `--json` is runtime-owned, it is hidden from the generated public API. The generated runtime creates the temporary result file, passes its path to the APE, waits for readiness, and cleans it up with the session.

If an APE also exposes a JSONL event stream, the same operation can declare that transport without making the event-file path part of the public API:

```yaml
events:
  source:
    kind: jsonl_file
    option_flag: --events
  discriminator: event
  types:
    - name: progress
      source_value: progress
      fields:
        - name: bytes
          api_name: bytes_processed
          value_type: integer
        - name: rate
          api_name: rate
          value_type: float
          required: false
```

The event names and field mappings are application semantics supplied by the schema author. APEBind owns the generic transport, decoding, lifecycle, and projection into each target language.

### 3. Validate

```bash
apebind validate ./examples/fixture.apebind.yaml
```

The schema loader is strict. Unknown fields, invalid scalar types, malformed command trees, duplicate names, ambiguous runtime-owned options, and unsupported lifecycle/result combinations fail fast.

### 4. Generate a Python package

```bash
apebind generate ./examples/fixture.apebind.yaml \
    --ape ./tests/fixtures/ape_fixture.com \
    --lang python \
    -o ./generated/fixturebind
```

The output is a normal Python project:

```text
generated/fixturebind/
├── pyproject.toml
├── README.md
└── src/
    └── fixturebind/
        ├── __init__.py
        ├── _generated.py
        ├── _runtime.py
        └── bin/
            └── fixture.com
```

Use it like a library:

```python
import fixturebind

print(fixturebind.echo(['hello', 'world'], upper=True))
print(fixturebind.json_value(value='hello'))

with fixturebind.serve(message='ready') as session:
    print(session.result)
```

Every generated package also has a raw escape hatch for commands or flags not yet modeled in the schema:

```python
result = fixturebind.raw(['echo', 'raw'])
print(result.stdout)
```

### Node.js

Generate the same fixture as a dependency-free ESM package with TypeScript declarations:

```bash
apebind generate ./examples/fixture.apebind.yaml \
    --ape ./tests/fixtures/ape_fixture.com \
    --lang node \
    -o ./generated/fixturebind-js

npm install ./generated/fixturebind-js
```

Then call the same APE through normal JavaScript:

```js
import { echo, jsonValue, serve } from 'fixturebind';

console.log(await echo({ text: ['hello', 'world'], upper: true }));
console.log(await jsonValue({ value: 'hello' }));

const session = await serve({ message: 'ready' });
console.log(session.result);
await session.stop();
```

When an operation declares events, `ProcessSession` also exposes the normal Node.js event surface:

```js
session.on('progress', (event) => {
  console.log(event.bytesProcessed, event.rate);
});

for await (const event of session.events()) {
  console.log(event.name, event.data);
}

await session.done;
```

Schema `snake_case` API names are projected to normal JavaScript `camelCase`; for example `json_value` becomes `jsonValue()` and `bytes_processed` becomes `bytesProcessed`. The `javascript`, `js`, and `nodejs` language names are aliases of `node`.

### A fun example: use `python.com` from Node.js

The repository also ships `ape/python.com`. `examples/python/python.discovered.apebind.yaml` records the raw help-import result, while `examples/python/python.apebind.yaml` is the reviewed schema used to generate a normal Node.js API around the portable interpreter:

```bash
./ape/apebind.com validate ./examples/python/python.apebind.yaml

./ape/apebind.com generate ./examples/python/python.apebind.yaml \
    --ape ./ape/python.com \
    --lang node \
    -o ./generated/python-ape

npm install ./generated/python-ape
```

The generated package bundles `python.com`, so JavaScript can run that self-contained Python runtime without requiring a separate system Python installation:

```js
import { run } from 'python-ape';

const result = await run({
  code: 'print(6 * 7)',
  isolated: true,
});

console.log(result.stdout.trim()); // 42
```

The checked-in schema also exposes module execution, script files, script arguments, unbuffered mode, and version reporting. See [`examples/languages/python/`](examples/languages/python/) for the schema and runnable JavaScript sample.

This is deliberately a subprocess boundary, not in-process CPython embedding. Still, from a distribution point of view it is a pleasantly strange result: an npm package can carry one portable Python runtime and expose it to JavaScript through a generated typed binding.

### Java / JVM

Generate the fixture as a dependency-free Java 17 Maven project:

```bash
apebind generate ./examples/fixture.apebind.yaml \
    --ape ./tests/fixtures/ape_fixture.com \
    --lang java \
    -o ./generated/fixturebind-java
```

The APE is bundled as a JAR resource and extracted to a temporary executable path on first use. Generated APIs use normal camelCase names and builder parameter objects:

```java
import apebind.generated.fixturebind.FixturebindBinding;

var parameters = FixturebindBinding.EchoParameters.builder()
    .text("hello")
    .text("world")
    .upper(true)
    .build();

System.out.println(FixturebindBinding.echo(parameters));
```

Persistent operations return `ProcessSession`, which implements `AutoCloseable`, so Java callers can use try-with-resources. Event-capable sessions expose `on(...)`, `eventHistory()`, and `done()`. The `jvm` language name is an alias of `java`.

## Architecture and schema

- [Architecture](docs/ARCHITECTURE.md)
- [Schema v1](docs/SCHEMA.md)
- [Recursive help importer](docs/HELP_IMPORTER.md)

The central separation is:

```text
APE
 │
 ▼
APEInspector
 │
 ▼
APEBindSpec  ← editable YAML / JSON
 │
 ▼
BindingModelBuilder
 │
 ▼
GeneratorRegistry
 │
 ├── PythonGenerator → Python project + bundled APE
 ├── NodeGenerator   → npm project + bundled APE
 └── JavaGenerator   → Maven/JAR project + bundled APE
```

`commands` describe the executable grammar. `operations` describe the programmer-facing API. A root CLI command can therefore become `share()`, `serve()`, or another semantic library operation without pretending the CLI tree itself is the library design.

## Tests

The full suite requires the repository-local Cosmopolitan toolchain (or `COSMOCC`) to build its APE fixture:

```bash
python scripts/build_ape_fixture.py
python scripts/test.py --group common
python scripts/test.py --group python
python scripts/test.py --group node
python scripts/test.py --group java
```

or simply bootstrap a new checkout:

```bash
python scripts/bootstrap.py
```

The backend tests are separated under `tests/generation/`. Python tests build/install a wheel; Node tests run the generated ESM package and perform `npm pack -> clean install -> bundled APE` coverage; Java tests compile the generated Maven sources and perform `JAR -> clean consumer -> bundled APE` coverage.

The repository also tests APEBind's self-application property: `apebind.com` inspects itself, generates a typed binding for itself, and that generated binding invokes the bundled `apebind.com` to generate another binding generation.

## Current v0.4 boundary

Implemented:

```text
APE -> inspect -> YAML/JSON schema -> Python / Node / Java SDK -> bundled APE subprocess
```

Not implemented yet:

- .NET, Rust, Go, C, or other language backends.
- Event transports other than runtime-owned JSONL files, such as HTTP hooks.
- Generic ELF/Mach-O/PE packaging.
- Machine-readable Usage Spec / CLI Spec importers.
- Framework-specific introspection plugins.
- Automatic inference of application-specific result/event semantics from arbitrary human help text.
