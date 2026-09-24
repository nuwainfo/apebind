# Ruby APE -> Node.js

Generate `ruby-ape`, install it in a Node project, then run `run.mjs`.

The example evaluates `puts 6 * 7` in the bundled Ruby runtime and prints
`42` without requiring a system Ruby installation.

## Runtime source and license

The `ruby.com` APE used by this example is distributed by
[Largo/cosmoruby](https://github.com/Largo/cosmoruby). CosmoRuby is released
under the [ISC License](https://github.com/Largo/cosmoruby/blob/main/LICENSE).
Review and satisfy that project's license terms when redistributing a generated
package that bundles its runtime.
