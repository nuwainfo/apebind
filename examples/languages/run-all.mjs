import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { run as runJanet } from 'janet-ape';
import { run as runLua } from 'lua-ape';
import { run as runPHP } from 'php-ape';
import { run as runPython } from 'python-ape';
import { run as runTcl } from 'tcl-ape';

const results = {};

results.janet = (await runJanet({ code: '(print (* 6 7))' })).stdout.trim();
results.lua = (await runLua({ code: 'print(6 * 7)', ignoreEnvironment: true })).stdout.trim();
results.php = (await runPHP({ code: 'echo 6 * 7;', noConfiguration: true })).stdout.trim();
results.python = (await runPython({ code: 'print(6 * 7)', isolated: true })).stdout.trim();

const directory = await mkdtemp(join(tmpdir(), 'tcl-ape-example-'));
const script = join(directory, 'answer.tcl');

try {
  await writeFile(script, 'puts [expr {6 * 7}]\n', 'utf8');

  results.tcl = (await runTcl({ file: script })).stdout.trim();
} finally {
  await rm(directory, { recursive: true, force: true });
}

console.log(results);
