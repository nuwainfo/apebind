import { start } from 'redbean-ape';


const server = await start({
  directory: './public',
});

console.log(server.url);

await server.stop();
