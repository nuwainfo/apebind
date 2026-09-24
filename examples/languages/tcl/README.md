# Tcl APE -> Node.js

Generate `tcl-ape`, install it in a Node project, then run `run.mjs`.

`tclsh` does not provide a command-line eval flag, so the example writes a temporary Tcl script, executes it with the bundled runtime, prints `42`, and removes the temporary file.
