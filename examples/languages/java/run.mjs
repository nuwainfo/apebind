import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { run } from 'java-ape';


const ANSWER_CLASS = Buffer.from(
  'yv66vgAAAEEAGwoAAgADBwAEDAAFAAYBABBqYXZhL2xhbmcvT2JqZWN0AQAGPGluaXQ+AQADKClWCQAIAAkHAAoMAAsADAEAEGphdmEvbGFuZy9TeXN0ZW0BAANvdXQBABVMamF2YS9pby9QcmludFN0cmVhbTsKAA4ADwcAEAwAEQASAQATamF2YS9pby9QcmludFN0cmVhbQEAB3ByaW50bG4BAAQoSSlWBwAUAQAGQW5zd2VyAQAEQ29kZQEAD0xpbmVOdW1iZXJUYWJsZQEABG1haW4BABYoW0xqYXZhL2xhbmcvU3RyaW5nOylWAQAKU291cmNlRmlsZQEAC0Fuc3dlci5qYXZhACAAEwACAAAAAAACAAAABQAGAAEAFQAAAB0AAQABAAAABSq3AAGxAAAAAQAWAAAABgABAAAAAQAJABcAGAABABUAAAAlAAIAAQAAAAmyAAcQKrYADbEAAAABABYAAAAKAAIAAAADAAgABAABABkAAAACABo=',
  'base64',
);

const directory = await mkdtemp(join(tmpdir(), 'java-ape-example-'));

try {
  await writeFile(join(directory, 'Answer.class'), ANSWER_CLASS);

  const result = await run({
    classPath: directory,
    mainClass: 'Answer',
  });

  console.log(result.stdout.trim());
} finally {
  await rm(directory, { recursive: true, force: true });
}
