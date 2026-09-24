# Help importer

`apebind inspect` imports a CLI's human-readable help as a starting point, not
as a trusted API specification. The resulting schema is expected to be
reviewed before generation.

## Discovery

Inspection starts with `tool.com --help`, adds described subcommands to a
breadth-first queue, then invokes each child with `--help`. Paths are
de-duplicated. It does not probe values merely because they appear in a choice
list: `{fast, slow}` is normally a positional choice, not evidence of commands.

Commands omitted from every help surface cannot be inferred safely. Supply
them as explicit seeds:

```bash
apebind inspect ./tool.com --output tool.apebind.yaml \
    --command repair \
    --command "admin reset"
```

For a maintained inventory, use a YAML file:

```yaml
commands:
  - repair
  - "admin reset"
  - [admin, user]
```

`--command` and `--command-file` combine in discovery order. Missing parents
are inspected first, and a seeded parent remains recursive. When a usage line
identifies the requested path, the importer verifies it; this rejects CLIs that
silently return unrelated help with exit status zero.

## Parsing limits and deliberate rules

The parser recognizes common argparse, Click/clap, and Cobra headings. Click
often puts positionals only in `Usage:`; these are imported when no explicit
positional section exists. Launcher spelling such as `python -m module` is not
made part of the command path, and generic placeholders (`[OPTIONS]`,
`COMMAND`, `[ARGS]...`) never become public positionals.

Some programs route root help to a primary command. A named section is promoted
to a command only when its usage prefix contains one literal command, a
top-level section has that same name, and that section has parseable arguments
or options. This preserves token placement: options belonging to the promoted
command are emitted after that command token.

Help text cannot reliably establish scalar types, defaults, repeatability,
hidden commands, output protocols, or persistent lifecycle. Command seeds only
solve inventory. The reviewed schema supplies the semantic layer.

## Extensibility

The importer, domain schema, and generators are independent so future importers
can create the same schema from a Usage Spec, CLI Spec, or application-provided
introspection JSON.
