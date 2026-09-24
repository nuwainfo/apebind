# Schema v1

The schema is the reviewed contract between an APE's executable grammar and a
generated library. It accepts YAML or JSON, uses `snake_case` neutral names,
and is strict: unknown keys and wrong scalar types are errors.

```yaml
schema_version: 1
ape:
  name: tool
  binary: tool.com
commands:
  - path: []
    options: []
    positionals: []
operations: []
```

`ape.binary` is a filename, not a source path. The `--ape` generation argument
selects the file to bundle under that package-data name. Every schema needs the
root command `path: []`; each child command requires its parent path.

## Commands and operations

`commands` preserve executable grammar. A command owns its `positionals` and
`options`, with `flags`, `api_name`, `value_type`, `required`, `multiple`, and
optionally `value_optional`. Supported value types are `string`, `integer`,
`float`, `path`, and `boolean`.

`operations` define the public library surface and reference a command path:

```yaml
- name: serve
  command: [serve]
  execution: persistent
  result:
    format: json_file
    option_flag: --json
    field: link
    ready_timeout_seconds: 10
```

An operation name need not mirror the command name. Parameters are collected
from its command chain; backends project neutral identifiers into their normal
language conventions. Boolean options emit only when true; repeated valued
options emit one flag/value pair per value. `value_optional: true` represents a
flag that may appear alone or with a value: false/null omits it, true emits the
flag, and another value emits the flag and value.

## Results and lifecycle

One-shot results are `command`, `text`, `json`, or `json_file`. `json` may use
a dotted `field`; `json_file` gives the runtime a temporary output path through
the declared `option_flag`. Persistent operations support only `command` and
`json_file`; with `ready_timeout_seconds`, they return after the JSON file is
stable and non-empty, making the session result available immediately.

One-shot operations may set a positive `process.timeout_seconds`. Persistent
operations deliberately cannot: their lifecycle belongs to the caller.

## Runtime-owned transports

An option used for a JSON result or JSONL events must match exactly one option
on the operation's command chain. APEBind then hides it from the generated
public API and owns its path and cleanup. Result and event transports cannot
own the same option.

```yaml
events:
  source:
    kind: jsonl_file
    option_flag: --events
  discriminator: type
  types:
    - name: progress
      source_value: upload_progress
      fields:
        - name: payload.bytes
          api_name: bytes_sent
          value_type: integer
```

The discriminator and field `name` values are dotted paths in each JSON object.
Declared fields are type-checked; missing required fields or malformed records
fail the session. Unknown discriminator values remain available as unknown
events. Event names and projections are application semantics chosen during
schema review, not facts inferred from help text.

## Runtime policy

Use `runtime.env_unset` when an embedded APE must not inherit selected
environment variables:

```yaml
runtime:
  env_unset: [PYTHONHOME, PYTHONPATH]
```

The generated runtime removes these values from a copy of the caller
environment for generated operations and `raw()` calls. See
[`examples/fixture.apebind.yaml`](../examples/fixture.apebind.yaml) for a
complete reviewed schema.
