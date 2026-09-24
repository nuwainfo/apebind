import { run } from 'lua-ape';

const result = await run({
  code: 'print(6 * 7)',
  ignoreEnvironment: true,
});

console.log(result.stdout.trim());
