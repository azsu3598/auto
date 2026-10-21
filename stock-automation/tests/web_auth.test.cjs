const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');
const { setTimeout: pause } = require('node:timers/promises');
const source = fs.readFileSync(path.join(__dirname, '../web/auth.js'), 'utf8');

function environment({search = '', attempt, tokenResponse, config} = {}) {
  const nodes = [];
  class Element {
    constructor(tag) { this.tag = tag; this.children = []; this.listeners = {}; nodes.push(this); }
    append(...children) { this.children.push(...children); }
    setAttribute() {}
    addEventListener(name, fn) { this.listeners[name] = fn; }
    remove() { this.removed = true; }
  }
  const actions = new Element('div');
  const document = {
    body: new Element('body'), createElement: (tag) => new Element(tag),
    getElementById: (id) => nodes.find((node) => node.id === id && !node.removed),
    querySelector: () => actions
  };
  const storage = new Map(attempt ? [['sabu-pkce', JSON.stringify(attempt)]] : []);
  const calls = []; const redirects = [];
  const ctx = {
    window: { SABU_CONFIG: config || { clientId: 'public-client', authOrigin: 'https://sign-in.example', apiOrigin: 'https://api.example' } },
    document, crypto: webcrypto, TextEncoder, Uint8Array, URL, URLSearchParams,
    btoa: (value) => Buffer.from(value, 'binary').toString('base64'),
    location: { origin: 'https://viewer.example', pathname: '/', search,
      assign: (value) => redirects.push(value), replace: (value) => redirects.push(value) },
    history: { replaceState() { ctx.location.search = ''; } },
    sessionStorage: { getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value), removeItem: (key) => storage.delete(key) },
    fetch: async (url, options) => {
      calls.push({ url: String(url), options });
      return String(url).includes('/oauth2/token')
        ? { ok: true, json: async () => tokenResponse || { access_token: 'test-access-token', token_type: 'Bearer', expires_in: 300 } }
        : { ok: true, status: 200, json: async () => ({}) };
    }
  };
  vm.createContext(ctx); vm.runInContext(source, ctx);
  return { ctx, nodes, storage, calls, redirects, actions };
}
async function until(fn) { for (let i = 0; i < 1000; i++) { if (fn()) return; await pause(1); } throw new Error('Test deadline'); }

test('sign-in uses unpredictable state and a matching SHA-256 PKCE challenge', async () => {
  const e = environment(); await until(() => e.nodes.some((node) => node.textContent === '로그인'));
  e.nodes.find((node) => node.textContent === '로그인').listeners.click();
  await until(() => e.redirects.length);
  const target = new URL(e.redirects[0]); const attempt = JSON.parse(e.storage.get('sabu-pkce'));
  assert.equal(target.searchParams.get('response_type'), 'code');
  assert.equal(target.searchParams.get('code_challenge_method'), 'S256');
  assert.equal(target.searchParams.get('state'), attempt.state);
  const hash = await webcrypto.subtle.digest('SHA-256', new TextEncoder().encode(attempt.verifier));
  assert.equal(target.searchParams.get('code_challenge'), Buffer.from(hash).toString('base64url'));
  assert.equal(e.calls.length, 0);
});

test('wrong callback state never exchanges the code or reads the ledger', async () => {
  const e = environment({search: '?code=test-code&state=wrong', attempt: { verifier: 'test-verifier', state: 'expected', created: Date.now() }});
  await until(() => e.ctx.document.getElementById('sign-in-message'));
  assert.equal(e.calls.length, 0); assert.equal(e.storage.size, 0); assert.equal(e.ctx.location.search, '');
});

test('successful callback uses only a memory token and logout clears it', async () => {
  const e = environment({search: '?code=test-code&state=expected', attempt: { verifier: 'test-verifier', state: 'expected', created: Date.now() }});
  await until(() => e.actions.children.length);
  await e.ctx.window.sabuDashboardFetch();
  const read = e.calls.find((call) => call.url.endsWith('/api/dashboard'));
  assert.equal(read.options.headers.Authorization, 'Bearer test-access-token');
  assert.equal(e.storage.size, 0); assert.equal(e.ctx.location.search, '');
  const post = e.calls.find((call) => call.url.endsWith('/oauth2/token'));
  assert.equal(post.options.body.get('code_verifier'), 'test-verifier');
  e.actions.children[0].listeners.click();
  assert.ok(e.redirects[0].includes('/logout?'));
  await assert.rejects(e.ctx.window.sabuDashboardFetch(), /expired/);
});

test('HTTP configuration cannot send the sign-in request or a token', async () => {
  const e = environment({ config: { clientId: 'public', authOrigin: 'http://unsafe.example', apiOrigin: 'https://api.example' } });
  await until(() => e.nodes.some((node) => node.textContent === '로그인'));
  e.nodes.find((node) => node.textContent === '로그인').listeners.click();
  await pause(10); assert.equal(e.redirects.length, 0); assert.equal(e.calls.length, 0);
});
