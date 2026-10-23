"use strict";
// PC-C only: node --test stock-automation/recommendation-lab/tests/web_client.test.cjs
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../web/app.js"), "utf8");
const html = fs.readFileSync(path.join(__dirname, "../web/index.html"), "utf8");

class Element {
  constructor() { this.textContent = ""; this.children = []; this.listeners = {}; this.disabled = false; this.hidden = false; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute() {}
  addEventListener(key, fn) { this.listeners[key] = fn; }
  click() { return this.listeners.click?.(); }
}

function result() {
  return { purpose: "RESEARCH_ONLY", order_submission: false, ledger_mutation: false,
    is_sample: true, rule_version: "test-unvalidated", status: "CANDIDATES",
    data_cutoff_at: new Date().toISOString(), expires_at: new Date(Date.now() + 30000).toISOString(),
    research_capital_krw: 600000, allocated_krw: 100000, remaining_cash_krw: 500000,
    candidates: [{ code: "DEMO_A", name: "가상 A기업", venue: "KRX", session: "REGULAR",
      observed_at: new Date().toISOString(), reference_price: 12500, entry_low: 12400, entry_high: 12500,
      suggested_quantity: 8, allocation_krw: 100000, stop_price: 12200, emergency_stop: 12100,
      stop_mode: "5M_CONFIRMED", emergency_stop_mode: "IMMEDIATE", target1: 13200, target2: 13600,
      reasons: ["가상 근거"], risks: ["검증 전"], sources: ["https://example.invalid/fictional"] }],
  };
}

function setup(fetcher) {
  const nodes = Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map((match) => [match[1], new Element()]));
  const tasks = new Map(), calls = []; let next = 0;
  const context = {
    document: {
      getElementById(id) { assert.ok(nodes[id], "Missing HTML element: " + id); return nodes[id]; },
      createElement() { return new Element(); }, querySelector() { return { content: "test-csrf" }; },
    },
    Date, Number, JSON, AbortController,
    crypto: { randomUUID: () => "2cd4e438-ad28-4d93-b221-00c7d60299ce" },
    fetch(...args) { calls.push(args); return fetcher ? fetcher(...args) : Promise.resolve({ ok: true, json: async () => result() }); },
    setTimeout(fn, delay) { tasks.set(++next, { fn, delay }); return next; },
    clearTimeout(id) { tasks.delete(id); },
  };
  vm.runInNewContext(source, context);
  return { nodes, tasks, calls };
}

test("initial load does not make an analysis request or schedule polling", () => {
  const s = setup(); assert.equal(s.calls.length, 0); assert.equal(s.tasks.size, 0);
});
test("manual request has only request id and local CSRF protection", async () => {
  const s = setup(); await s.nodes.run.click();
  assert.equal(s.calls.length, 1); assert.equal(s.calls[0][0], "/api/recommendations");
  const options = s.calls[0][1]; assert.equal(options.method, "POST");
  assert.deepEqual(Object.keys(JSON.parse(options.body)), ["request_id"]);
  assert.equal(options.headers["X-Recommendation-CSRF"], "test-csrf");
  assert.equal(s.nodes.cards.children.length, 1); assert.equal(s.nodes.run.disabled, false);
});
test("duplicate click during an active request does not send a second request", async () => {
  let complete;
  const s = setup(() => new Promise((resolve) => { complete = resolve; }));
  const first = s.nodes.run.click(); await s.nodes.run.click(); assert.equal(s.calls.length, 1);
  complete({ ok: true, json: async () => result() }); await first;
});
test("server BLOCKED is not displayed as a successful NO_TRADE", async () => {
  const s = setup(async () => ({ ok: false, json: async () => ({ status: "BLOCKED", reason: "DATA_SOURCE_NOT_CONNECTED" }) }));
  await s.nodes.run.click(); assert.equal(s.nodes.cards.children.length, 0);
  assert.match(s.nodes["result-heading"].textContent, /BLOCKED/);
  assert.match(s.nodes.status.textContent, /DATA_SOURCE_NOT_CONNECTED/);
});
test("expired or malformed numeric payload fails closed", async () => {
  for (const mutation of [
    (data) => { data.expires_at = new Date(0).toISOString(); },
    (data) => { data.candidates[0].entry_low = null; },
    (data) => { data.order_submission = true; },
    (data) => { data.status = "NO_TRADE"; },
    (data) => { delete data.is_sample; },
  ]) {
    const data = result(); mutation(data);
    const s = setup(async () => ({ ok: true, json: async () => data })); await s.nodes.run.click();
    assert.equal(s.nodes.cards.children.length, 0); assert.equal(s.nodes["result-heading"].textContent, "결과 없음");
  }
});
test("expiry hides results without a new automatic request", async () => {
  const s = setup(); await s.nodes.run.click();
  assert.equal(s.tasks.size, 1); [...s.tasks.values()][0].fn();
  assert.equal(s.nodes.cards.children.length, 0); assert.equal(s.calls.length, 1);
  assert.match(s.nodes["result-heading"].textContent, /결과 만료/);
});
test("cancel stops waiting and a late response cannot repopulate cards", async () => {
  let complete;
  const s = setup(() => new Promise((resolve) => { complete = resolve; }));
  const first = s.nodes.run.click(); s.nodes.cancel.click();
  complete({ ok: true, json: async () => result() }); await first;
  assert.equal(s.nodes.cards.children.length, 0); assert.equal(s.nodes.run.disabled, false);
  assert.match(s.nodes.status.textContent, /서버 작업이나 기존 매매의 중지가 아닙니다/);
});
test("network failure has no retries or residual candidate cards", async () => {
  const s = setup(async () => { throw new Error("connection failed"); }); await s.nodes.run.click();
  assert.equal(s.calls.length, 1); assert.equal(s.nodes.cards.children.length, 0); assert.equal(s.tasks.size, 0);
  assert.match(s.nodes.status.textContent, /자동 재시도하지 않습니다/);
});
