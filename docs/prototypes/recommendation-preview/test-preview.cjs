"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const dist = path.join(__dirname, "dist");
const source = fs.readFileSync(path.join(dist, "preview.js"), "utf8");
const html = fs.readFileSync(path.join(dist, "index.html"), "utf8");

class Element {
  constructor() { this.children = []; this.attributes = {}; this.listeners = {}; this.textContent = ""; this.hidden = false; this.disabled = false; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; this.textContent = ""; }
  setAttribute(key, value) { this.attributes[key] = value; }
  addEventListener(name, handler) { this.listeners[name] = handler; }
  click() { this.listeners.click?.(); }
}

function setup(scenario = "candidates") {
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]);
  const nodes = Object.fromEntries(ids.map((id) => [id, new Element()]));
  nodes.scenario.value = scenario;
  const tasks = new Map(); let nextId = 0;
  const document = {
    getElementById(id) { assert.ok(nodes[id], "Missing HTML id: " + id); return nodes[id]; },
    createElement() { return new Element(); },
  };
  const context = {
    document, Intl, Date,
    setTimeout(fn, delay) { tasks.set(++nextId, { fn, delay }); return nextId; },
    clearTimeout(id) { tasks.delete(id); },
  };
  vm.runInNewContext(source, context);
  return { nodes, tasks, settle() { const pending = [...tasks.values()]; tasks.clear(); for (const task of pending) task.fn(); } };
}

function text(node) { return node.textContent + node.children.map(text).join(" "); }

test("opens idle without work, external services, or candidate cards", () => {
  const s = setup(); assert.equal(s.tasks.size, 0); assert.equal(s.nodes.cards.children.length, 0);
});
test("starts only on explicit click and rejects duplicate requests", () => {
  const s = setup(); s.nodes.run.click(); s.nodes.run.click();
  assert.equal(s.tasks.size, 1); assert.equal(s.nodes.run.disabled, true); assert.equal(s.nodes.scenario.disabled, true);
  assert.equal(s.nodes["result-panel"].attributes["aria-busy"], "true");
});
test("renders two fictional cards and releases controls", () => {
  const s = setup(); s.nodes.run.click(); s.settle();
  assert.equal(s.nodes.cards.children.length, 2); assert.equal(s.nodes.run.disabled, false); assert.equal(s.nodes.cancel.hidden, true);
  assert.match(text(s.nodes.cards), /DEMO_A/); assert.match(text(s.nodes.cards), /DEMO_B/); assert.match(text(s.nodes.cards), /실제 상장종목 아님/);
  assert.match(text(s.nodes.summary), /389,200원/); assert.match(text(s.nodes.cards), /5M_CONFIRMED/); assert.match(text(s.nodes.cards), /IMMEDIATE/);
});
test("NO_TRADE has no candidates, zero allocation and all cash", () => {
  const s = setup("no_trade"); s.nodes.run.click(); s.settle();
  assert.equal(s.nodes.cards.children.length, 0); assert.match(s.nodes["result-title"].textContent, /NO_TRADE/);
  assert.match(text(s.nodes.summary), /0원 · 0%/); assert.match(text(s.nodes.summary), /600,000원 · 100%/);
});
for (const [scenario, title] of [["stale", "추천 차단"], ["timeout", "시간 초과"], ["error", "조회 실패"], ["invalid", "조회 실패"]]) {
  test(scenario + " hides candidates and is not successful NO_TRADE", () => {
    const s = setup(scenario); s.nodes.run.click(); s.settle();
    assert.equal(s.nodes.cards.children.length, 0); assert.equal(s.nodes.summary.hidden, true);
    assert.ok(s.nodes["result-title"].textContent.includes(title)); assert.equal(s.tasks.size, 0);
    assert.doesNotMatch(s.nodes["result-title"].textContent, /NO_TRADE/);
  });
}
test("new request discards previous candidates immediately", () => {
  const s = setup(); s.nodes.run.click(); s.settle(); s.nodes.scenario.value = "stale"; s.nodes.run.click();
  assert.equal(s.nodes.cards.children.length, 0); assert.equal(s.nodes.summary.hidden, true); s.settle();
  assert.equal(s.nodes.cards.children.length, 0);
});
test("cancel clears pending work without showing a result", () => {
  const s = setup(); s.nodes.run.click(); s.nodes.cancel.click(); s.settle();
  assert.equal(s.tasks.size, 0); assert.equal(s.nodes.cards.children.length, 0); assert.equal(s.nodes.run.disabled, false);
  assert.match(s.nodes.status.textContent, /운영 중인 작업이나 매매를 중지하는 버튼이 아닙니다/);
});
test("a canceled callback cannot overwrite a newer request", () => {
  const s = setup(); s.nodes.run.click(); const old = [...s.tasks.values()][0].fn; s.nodes.cancel.click();
  s.nodes.scenario.value = "no_trade"; s.nodes.run.click(); old();
  assert.equal(s.nodes.cards.children.length, 0); assert.equal(s.nodes.run.disabled, true);
  s.settle(); assert.match(s.nodes["result-title"].textContent, /NO_TRADE/);
});
test("result timestamp explicitly is not a quote timestamp", () => {
  const s = setup(); s.nodes.run.click(); s.settle();
  assert.match(s.nodes["viewed-at"].textContent, /시연 완료 시각/); assert.match(s.nodes["viewed-at"].textContent, /실제 시세 기준 시각 없음/);
});
test("sample contains no networking, storage, dynamic HTML or recurring work", () => {
  assert.doesNotMatch(source, /\b(fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon|localStorage|sessionStorage|indexedDB|setInterval|eval)\b|innerHTML|import\s*\(|require\s*\(/);
  assert.doesNotMatch(html, /https?:\/\/|<form\b|<iframe\b|<img\b|onclick=/i);
  assert.match(html, /connect-src 'none'/); assert.match(html, /가상 종목 · 가상 가격 · 실제 추천이 아닙니다/);
  assert.match(html, /<button id="run"[^>]*type="button"/);
  assert.match(html, /<button id="cancel"[^>]*hidden/);
  assert.match(html, /<section id="progress"[^>]*hidden/);
});
test("HTML ids are unique and runtime references are real", () => {
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]);
  assert.equal(ids.length, new Set(ids).size); setup();
});
test("local assets exist and contain responsive and accessible states", () => {
  for (const name of ["preview.css", "preview.js"]) assert.ok(fs.existsSync(path.join(dist, name)));
  const css = fs.readFileSync(path.join(dist, "preview.css"), "utf8");
  assert.match(css, /max-width: 560px/); assert.match(css, /max-width: 900px/); assert.match(css, /focus-visible/);
  assert.match(css, /prefers-reduced-motion/); assert.match(html, /aria-live="polite"/); assert.match(html, /<label for="scenario"/);
});
