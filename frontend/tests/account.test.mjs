import { test } from "node:test";
import assert from "node:assert/strict";
import { build } from "esbuild";
async function client(user = "alice") {
  const result = await build({
    entryPoints: ["src/services/accountApi.ts"],
    bundle: true,
    write: false,
    format: "esm",
    platform: "browser",
    define: {
      "import.meta.env.VITE_REST_API_URL": JSON.stringify(
        "https://api.rest.example",
      ),
    },
    plugins: [
      {
        name: "session",
        setup(b) {
          b.onResolve({ filter: /cloudSession$/ }, () => ({
            path: "session",
            namespace: "fixture",
          }));
          b.onLoad({ filter: /.*/, namespace: "fixture" }, () => ({
            contents: `export const supabase={auth:{getSession:async()=>({data:{session:{user:{id:${JSON.stringify(user)}},access_token:'test-token'}}})}};`,
          }));
        },
      },
    ],
  });
  return import(
    `data:text/javascript;base64,${Buffer.from(result.outputFiles[0].text).toString("base64")}#${Math.random()}`
  );
}
test("account switch prevents a pending action from using the new account", async () => {
  const api = await client("bob");
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
  };
  await assert.rejects(
    api.accountApi("/v1/routine", { method: "PUT", body: "{}" }, "alice"),
    /account changed/,
  );
  assert.equal(calls, 0);
});
test("writes use authenticated JSON and conflict errors are not success", async () => {
  const api = await client();
  globalThis.fetch = async (url, init) => {
    assert.equal(url, "https://api.rest.example/v1/routine");
    assert.equal(init.headers.get("Authorization"), "Bearer test-token");
    assert.equal(init.headers.get("Content-Type"), "application/json");
    assert.equal(init.cache, "no-store");
    return new Response(
      JSON.stringify({ error: { message: "Routine changed. Reload." } }),
      { status: 409 },
    );
  };
  await assert.rejects(
    api.accountApi("/v1/routine", { method: "PUT", body: "{}" }, "alice"),
    (e) => e.status === 409 && /Reload/.test(e.message),
  );
});
test("progress photo requests preserve multipart boundaries and private downloads", async () => {
  const api = await client();
  const data = new FormData(); data.set("metadata", "{}"); data.set("photo", new Blob(["fixture"], { type: "image/jpeg" }), "fixture.jpg");
  globalThis.fetch = async (_url, init) => {
    assert.equal(init.headers.get("Authorization"), "Bearer test-token");
    assert.equal(init.headers.has("Content-Type"), false);
    assert.equal(init.body, data);
    return new Response('{"id":"saved"}', { status: 200 });
  };
  assert.deepEqual(await api.accountApi('/v1/progress/photos', { method: 'POST', body: data }, 'alice'), { id: 'saved' });
  globalThis.fetch = async (url, init) => {
    assert.equal(url, 'https://api.rest.example/v1/progress/photos/photo-id/image');
    assert.equal(init.cache, 'no-store');
    assert.equal(init.headers.get('Authorization'), 'Bearer test-token');
    return new Response('jpeg-fixture', { headers: { 'Content-Type': 'image/jpeg' } });
  };
  const blob = await api.accountPhoto('photo-id', new AbortController().signal, 'alice');
  assert.equal(await blob.text(), 'jpeg-fixture');
});
