import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';

async function loadClient(cloudEnabled = true) {
  const result = await build({
    entryPoints: ['src/services/illustration.ts'], bundle: true, write: false, format: 'esm', platform: 'browser',
    define: { 'import.meta.env.VITE_REST_API_URL': JSON.stringify('https://api.rest.example') },
    plugins: [{ name: 'test-session', setup(builder) {
      builder.onResolve({ filter: /cloudSession$/ }, () => ({ path: 'session', namespace: 'test' }));
      builder.onLoad({ filter: /.*/, namespace: 'test' }, () => ({ contents: `export const cloudEnabled = ${cloudEnabled}; export async function accessToken() { return 'user-jwt'; }` }));
    } }],
  });
  return import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].text).toString('base64')}#${Math.random()}`);
}
const id = '37e441ea-c3d8-4f81-bdc4-c5b8b2b9cd1a';
const reply = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });

test('cloud submission records consent, binds options and sends a user token', async () => {
  const client = await loadClient();
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push([url, init]);
    return reply(calls.length === 1 ? {} : { id, status: 'queued' });
  };
  await client.createIllustration(new File(['photo'], 'photo.png'), {
    faceBox: [0,0,128,128], editBox: [20,20,40,40], strength: '0.15', finish: 'original', product: 'private note',
  }, new AbortController().signal);
  assert.equal(calls[0][0], 'https://api.rest.example/v1/consents/illustration');
  assert.equal(calls[1][0], 'https://api.rest.example/v1/illustrations');
  assert.equal(calls[1][1].headers.Authorization, 'Bearer user-jwt');
  assert.match(calls[1][1].headers['Idempotency-Key'], /^[0-9a-f-]{36}$/);
  assert.deepEqual(JSON.parse(calls[1][1].body.get('options')), { mode: 'face-edit', face_box:[0,0,128,128], edit_box:[20,20,40,40], strength:.15, finish:'original' });
  assert.equal(calls[1][1].body.get('product'), null);
});

test('private image request never follows a worker-supplied external URL', async () => {
  const client = await loadClient();
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push([url,init]);
    return url.endsWith('/image') ? new Response('png', {headers:{'Content-Type':'image/png'}}) : reply({ id, status:'completed', imageUrl:'https://untrusted.example/image' });
  };
  const job = await client.getIllustration(id, new AbortController().signal);
  assert.ok(job.imageUrl.startsWith('blob:'));
  assert.equal(calls[1][0], `https://api.rest.example/v1/jobs/${id}/image`);
  assert.equal(calls[1][1].headers.Authorization, 'Bearer user-jwt');
  await client.getIllustration(id, new AbortController().signal);
  assert.equal(calls.filter(([url]) => url.endsWith('/image')).length,1);
  client.releaseIllustrationImage(id);
});

test('cloud errors remain actionable and expired delete is idempotent', async () => {
  const client = await loadClient();
  globalThis.fetch = async () => reply({error:{message:'Queue is full.'}},429);
  await assert.rejects(client.getIllustration(id,new AbortController().signal), /Queue is full/);
  globalThis.fetch = async () => reply({},404);
  await client.deleteIllustration(id);
});

test('local preview retains its same-origin cookie session', async () => {
  const client = await loadClient(false);
  const calls = [];
  globalThis.fetch = async (url, init) => { calls.push([url,init]); return reply({id,status:'queued'}); };
  await client.createIllustration(new File(['photo'],'x.png'), {faceBox:[0,0,128,128],editBox:[20,20,40,40],strength:'0.15',finish:'original',product:''},new AbortController().signal);
  assert.equal(calls[0][0],'/illustration-api/session');
  assert.equal(calls[1][0],'/illustration-api/jobs');
  assert.equal(calls[1][1].headers,undefined);
});
