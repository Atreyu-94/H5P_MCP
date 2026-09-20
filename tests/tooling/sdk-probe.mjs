// Exact published SDK contract probe; does not implement Tasks or replace MCP.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { Client } from '@modelcontextprotocol/client';
import { StdioClientTransport } from '@modelcontextprotocol/client/stdio';
import { McpServer, InMemoryTransport } from '@modelcontextprotocol/server';

const [python, cwd] = process.argv.slice(2);
assert(python && cwd, 'Usage: node sdk-probe.mjs <python> <repository>');
const server = new McpServer({name:'f0-resource-probe', version:'1'});
server.registerResource('probe', 'test://baseline', {mimeType:'text/plain'}, async uri => ({
  contents:[{uri:uri.href, text:'baseline'}]
}));
const memoryClient = new Client({name:'f0-memory',version:'1'});
const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
try {
  await server.connect(serverTransport);
  await memoryClient.connect(clientTransport);
  assert.equal((await memoryClient.readResource({uri:'test://baseline'})).contents[0].text, 'baseline');
} finally {
  await memoryClient.close();
  await server.close();
}

// The extension schema here only checks the envelope. Explicit assertions below
// verify its payload; this is an interoperability probe, not a conformance suite.
const objectSchema = {'~standard': {version:1, vendor:'f0-probe', validate(value) {
  return value && typeof value === 'object' ? {value} : {issues:[{message:'Expected object'}]};
}}};
const client = new Client({name:'f0-python-interop', version:'1'}, {versionNegotiation:{mode:'auto'}});
const transport = new StdioClientTransport({command:python,args:['-m','h5p_mcp.server'],cwd,stderr:'pipe'});
try {
  await client.connect(transport);
  const capabilities = client.getServerCapabilities();
  assert.deepEqual(capabilities.extensions['io.modelcontextprotocol/skills'], {});
  const listed = await client.request({method:'skills/list', params:{}}, objectSchema);
  assert.equal(listed.skills.length, 1);
  const entry = listed.skills[0];
  const fetched = await client.request({method:'skills/get',params:{uri:entry.uri}}, objectSchema);
  assert.deepEqual(fetched.skill, entry);
  const resource = await client.readResource({uri:entry.uri});
  const text = resource.contents[0].text;
  assert.equal(Buffer.byteLength(text), entry.resources[0].size);
  assert.equal('sha256:' + createHash('sha256').update(text).digest('hex'), entry.resources[0].digest);
  assert(!capabilities.extensions['io.modelcontextprotocol/tasks']);
  console.log(JSON.stringify({sdk:'2.0.0',node:process.version,resourceRoundtrip:'passed',
    pythonSkillsRoundtrip:'passed',skillDigest:'passed',tasks:'not_advertised',
    tasksLifecycle:'not_run',conformance:'not_run'}));
} finally {
  await client.close();
}
