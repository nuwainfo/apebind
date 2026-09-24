import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { run } from 'tcl-ape';

const directory = await mkdtemp(join(tmpdir(), 'tcl-ape-example-'));
const script = join(directory, 'answer.tcl');

try {
  await writeFile(script, 'puts [expr {6 * 7}]\n', 'utf8');

  const result = await run({ file: script });

  console.log(result.stdout.trim());
} finally {
  await rm(directory, { recursive: true, force: true });
}
