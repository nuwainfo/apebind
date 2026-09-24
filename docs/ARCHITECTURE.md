# Architecture

APEBind turns an APE command-line surface into a generated package without
making the generated package depend on APEBind at runtime. It supports APEs
only; handling ordinary native binaries would reintroduce platform-specific
distribution concerns that APEs avoid.

## Pipeline

```text
APE file
  -> APEDetector -> ExecutableRunner -> HelpParser -> APEInspector
  -> APEBindSpec <-> SchemaCodec (YAML / JSON)
  -> BindingModelBuilder -> BindingModel
  -> GeneratorRegistry -> language backend -> generated package + bundled APE
```

These are intentional boundaries. Inspection imports executable grammar;
schema review supplies semantic API decisions; the binding model is neutral;
backends only project that model into a target language. A backend must not
teach the importer or schema about language-specific syntax.

## Ownership

`APEDetector` validates the APE header before inspection or generation.
`ExecutableRunner` is the inspection subprocess boundary: POSIX uses the shell
fallback required by shebang-less APEs, while Windows invokes the executable
directly.

`APEInspector` performs breadth-first discovery. Explicit command seeds and
automatically discovered commands use the same queue, so a seeded parent still
discovers the children its help describes. `HelpParser` only parses text; it
does not execute processes or define public API semantics.

`APEBindSpec` owns language-neutral invariants: command-tree integrity,
snake_case API names, operation references, result/lifecycle compatibility,
and runtime-owned options. `SchemaCodec` rejects unknown fields and invalid
scalar values instead of coercing them.

`BindingModelBuilder` is the shared generation boundary. It flattens command
chains, orders parameters, marks runtime-owned result/event options, and
produces process, result, and event metadata. Language backends consume this
model rather than recreating CLI semantics.

## Generated runtime contract

Generated packages own argv construction, process lifecycle, result decoding,
timeouts, runtime-owned temporary files, JSONL event decoding, and the raw argv
escape hatch. The original APE is copied into package data.

`commands` represent the executable syntax tree. `operations` represent the
programmer-facing API and may choose a different name or lifecycle for the same
command path. Application vocabulary—such as what a `progress` event means—is
specified by the reviewed schema, never inferred by the generic runtime.

The current backends are Python, Node.js, and Java. Their projects and runtimes
use only the target platform's standard facilities: Python standard library,
`node:*` modules, and Java 17 respectively.
