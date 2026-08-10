import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { isDuplicateTransaction, merchantSimilarity, normalizeMerchant } from "../lib/dedupe.ts";

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
  for (const text of ["SelfBank", "新增交易", "手機載具", "所有支出與收入", "全部收支", "全部分類", "本月預算", "每月固定收支", "固定收入", "固定支出"]) assert.match(html, new RegExp(text));
  assert.doesNotMatch(html, /Google 與 Apple 帳號|連結帳號|Apple／iCloud 帳號/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton|Starter Project/);
});

test("交易紀錄支援收支與分類交叉篩選", async () => {
  const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  assert.match(page, /categoryFilter/);
  assert.match(page, /只看支出/);
  assert.match(page, /只看收入/);
  assert.match(page, /全部分類/);
  assert.match(page, /shownSummary/);
  assert.doesNotMatch(page, /shown\.slice\(0,8\)/);
});

test("固定扣款保留，外部帳號連動已移除", async () => {
  const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  assert.match(page, /selfbank-v1-recurring/);
  assert.match(page, /每月固定支出/);
  assert.match(page, /每月固定收入/);
  assert.match(page, /recurringFilter/);
  assert.match(page, /name="type"/);
  assert.doesNotMatch(page, /setModal\("accounts"\)|Google 帳號|Apple／iCloud 帳號/);
});

test("v1 包含本機保存、CSV 匯入與載具驗證", async () => {
  const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  assert.match(page, /localStorage\.setItem\("selfbank-v1-transactions"/);
  assert.match(page, /reader\.readAsText\(file\)/);
  assert.ok(page.includes('pattern="/[0-9A-Z.+\\-]{7}"'));
  assert.match(page, /type: type === "income"/);
});

test("銀行交易會與載具發票去重，且避免誤判", () => {
  const invoice = { title: "全聯福利中心股份有限公司", amount: 1286, date: "2026-08-10", type: "expense", source: "雲端發票" };
  const bank = { title: "信用卡消費 全聯福利中心", amount: 1286, date: "2026-08-12", type: "expense", source: "CSV 匯入" };
  const differentAmount = { ...bank, amount: 1386 };
  const differentStore = { ...bank, title: "台灣高鐵" };
  assert.equal(normalizeMerchant(invoice.title), "全聯福利中心");
  assert.ok(merchantSimilarity(invoice.title, bank.title) >= 0.82);
  assert.equal(isDuplicateTransaction(bank, invoice), true);
  assert.equal(isDuplicateTransaction(differentAmount, invoice), false);
  assert.equal(isDuplicateTransaction(differentStore, invoice), false);
});
