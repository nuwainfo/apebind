import { run } from 'janet-ape';

const result = await run({
  code: '(print (* 6 7))',
});

console.log(result.stdout.trim());
