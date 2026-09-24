# Java APE -> Node.js

Generate `java-ape`, install it in a Node project, then run `run.mjs`.

The bundled Java APE is a runtime rather than a source-code interpreter or
compiler. This small packaging demonstration writes a precompiled
`Answer.class` to a temporary directory, runs it through the generated binding,
and prints `42` without requiring a system Java runtime. Build application
classes with your normal Java toolchain before running them through `java-ape`.
