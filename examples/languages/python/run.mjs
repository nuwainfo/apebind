import { run } from 'python-ape';

const result = await run({
  code: 'print(6 * 7)',
  isolated: true,
});

console.log(result.stdout.trim());
