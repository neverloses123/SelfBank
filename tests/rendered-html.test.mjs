import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(new Request("http://localhost/", { headers: { accept: "text/html" } }), { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } }, { waitUntil() {}, passThroughOnException() {} });
}

test("SelfBank 首頁可由伺服器正常輸出", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /<title>SelfBank｜我的個人記帳本<\/title>/i);
  for (const text of ["SelfBank", "新增交易", "手機載具", "最近交易", "本月預算"]) assert.match(html, new RegExp(text));
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton|Starter Project/);
});

test("v1 包含本機保存、CSV 匯入與載具驗證", async () => {
  const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  assert.match(page, /localStorage\.setItem\("selfbank-v1-transactions"/);
  assert.match(page, /reader\.readAsText\(file\)/);
  assert.ok(page.includes('pattern="/[0-9A-Z.+\\-]{7}"'));
  assert.match(page, /type: type === "income"/);
});
