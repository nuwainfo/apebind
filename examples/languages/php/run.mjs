import { run } from 'php-ape';

const result = await run({
  code: 'echo 6 * 7;',
  noConfiguration: true,
});

console.log(result.stdout.trim());
