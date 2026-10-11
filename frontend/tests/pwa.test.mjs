import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import { workerSource } from '../build/pwaPlugin.mjs';
import { build } from 'esbuild';

function worker() {
  const events = new Map(); const put = [];
  const cache = { match: async () => new Response('public shell'), put: async (...args) => put.push(args) };
  const context = {
    self: { location: { origin:'https://rest.example' }, addEventListener: (event, fn) => events.set(event,fn), clients:{claim:async()=>{}}, skipWaiting:()=>{} },
    URL, Request, Response, Set,
    caches: { open:async()=>cache, match:async()=>new Response('offline shell'), keys:async()=>[], delete:async()=>true },
    fetch:async()=>new Response('public asset'),
  };
  vm.runInNewContext(workerSource('fixture',['/index.html','/assets/app.js']),context);
  return {events,put,context};
}
test('service worker never handles API, photo, auth, uploads or foreign requests', () => {
  const { events } = worker();
  const cases = [
    ['https://rest.example/rest-api/v1/me',{}],
    ['https://rest.example/rest-api/v1/progress/photos/photo/image',{}],
    ['https://rest.example/illustration-api/jobs/abc/image',{}],
    ['https://rest.example/?reset=1',{}],
    ['https://rest.example/assets/app.js?token=private',{}],
    ['https://rest.example/assets/app.js',{headers:{Authorization:'Bearer test-only'}}],
    ['https://rest.example/assets/app.js',{method:'POST',body:'test-only'}],
    ['https://other.example/assets/app.js',{}],
  ];
  for (const [url,init] of cases) {
    let intercepted=false;
    events.get('fetch')({request:new Request(url,init),respondWith:()=>{intercepted=true;}});
    assert.equal(intercepted,false,url);
  }
});
test('offline public navigation falls back to shell without persisting personal responses', async () => {
  const {events,put,context}=worker(); context.fetch=async()=>{throw new Error('offline');};
  let response;
  events.get('fetch')({request:{url:'https://rest.example/',method:'GET',mode:'navigate',headers:new Headers()},respondWith:promise=>{response=promise;}});
  assert.equal(await (await response).text(),'offline shell');
  assert.equal(put.length,0);
});
test('manifest has real PNG icons and standalone launch settings', async () => {
  const manifest=JSON.parse(await readFile('public/manifest.webmanifest','utf8'));
  assert.equal(manifest.display,'standalone');assert.equal(manifest.id,'/');assert.equal(manifest.scope,'/');
  assert.equal(manifest.start_url,'/#overview');
  for (const item of manifest.icons) {
    const png=await readFile('public'+item.src);
    assert.equal(png.subarray(1,4).toString(),'PNG');
    const size=Number(item.sizes.split('x')[0]);
    assert.equal(png.readUInt32BE(16),size);assert.equal(png.readUInt32BE(20),size);
  }
  assert.ok(manifest.icons.some(icon=>icon.sizes==='192x192'));
  assert.ok(manifest.icons.some(icon=>icon.sizes==='512x512'&&icon.purpose==='maskable'));
});
test('install prompt is preserved until a user action and consumed only once', async () => {
  const events=new Map();
  const result=await build({entryPoints:['src/services/pwa.ts'],bundle:true,write:false,format:'esm',platform:'browser'});
  const original=globalThis.window;
  globalThis.window={ addEventListener:(name,fn)=>events.set(name,fn),matchMedia:()=>({matches:false}) };
  try {
    const pwa=await import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].text).toString('base64')}`);
    pwa.setupPwa(false);let prompted=0;
    events.get('beforeinstallprompt')({preventDefault(){},prompt:async()=>{prompted++;},userChoice:Promise.resolve({outcome:'accepted'})});
    assert.equal(pwa.pwaState().canPrompt,true);assert.equal(prompted,0);
    await pwa.installApp();await pwa.installApp();assert.equal(prompted,1);assert.equal(pwa.pwaState().canPrompt,false);
  } finally { globalThis.window=original; }
});
