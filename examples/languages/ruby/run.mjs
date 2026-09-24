import { run } from 'ruby-ape';

const result = await run({ code: 'puts 6 * 7' });

console.log(result.stdout.trim());
