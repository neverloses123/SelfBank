import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { isDuplicateTransaction, merchantSimilarity, normalizeMerchant } from "../lib/dedupe.ts";

async function render(path = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(new Request(`http://localhost${path}`, { headers: { accept: "text/html" } }), { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } }, { waitUntil() {}, passThroughOnException() {} });
}

test("SelfBank 首頁可由伺服器正常輸出", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /<title>SelfBank｜我的個人記帳本<\/title>/i);
  for (const text of ["SelfBank", "新增交易", "資料匯入", "所有支出與收入", "財務分析", "固定收支", "沒有符合條件的交易"]) assert.match(html, new RegExp(text));
  assert.doesNotMatch(html, /手機載具/);
  assert.doesNotMatch(html, /本月財務異常|最近 7 天|每月固定收入/);
  assert.doesNotMatch(html, /Google 與 Apple 帳號|連結帳號|Apple／iCloud 帳號/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton|Starter Project/);
});

test("固定收支與財務分析為獨立頁面", async () => {
  const recurringHtml = await (await render("/recurring")).text();
  for (const text of ["每月固定收入", "每月固定支出", "預估淨收入"]) assert.match(recurringHtml, new RegExp(text));
  assert.doesNotMatch(recurringHtml, /所有支出與收入|本月財務異常/);
  const analysisHtml = await (await render("/analysis")).text();
  for (const text of ["本月財務異常", "最近 7 天", "支出分析", "本月盈虧", "儲蓄率", "固定與可變支出", "預估月底總支出"]) assert.match(analysisHtml, new RegExp(text));
  assert.doesNotMatch(analysisHtml, /所有支出與收入|每月固定收入/);
});

test("交易紀錄支援收支與分類交叉篩選", async () => {
  const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  assert.match(page, /categoryFilter/);
  assert.match(page, /只看支出/);
  assert.match(page, /只看收入/);
  assert.match(page, /全部分類/);
  assert.match(page, /shownSummary/);
  assert.doesNotMatch(page, /shown\.slice\(0,8\)/);
  for (const text of ["備註", "編輯交易", "儲存修改", "交易只提供編輯，不提供刪除功能"]) assert.match(page, new RegExp(text));
  assert.match(page, /method: "PATCH"/);
  assert.match(page, /\/transactions\/\$\{editingTx\.id\}/);
  assert.doesNotMatch(page, /method: "DELETE"|刪除交易/);
  const api = await readFile(new URL("../backend/app/main.py", import.meta.url), "utf8");
  assert.match(api, /@app\.patch\("\/transactions\/\{item_id\}"\)/);
  assert.doesNotMatch(api, /@app\.delete/);
});

test("固定扣款保留，外部帳號連動已移除", async () => {
  const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  assert.match(page, /setRecurring/);
  assert.match(page, /每月固定支出/);
  assert.match(page, /每月固定收入/);
  assert.match(page, /recurringFilter/);
  assert.match(page, /name="type"/);
  assert.doesNotMatch(page, /setModal\("accounts"\)|Google 帳號|Apple／iCloud 帳號/);
});

test("v1 只保留 PDF 匯入並提供 PDF 匯出", async () => {
  const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(page, /localStorage|const seed|recurringSeed/);
  assert.match(page, /\/health/);
  assert.match(page, /health\.backend !== "sqlserver"/);
  assert.match(page, /health\.database !== "HomeAccounting"/);
  for (const field of ["類型", "名稱", "金額", "日期", "分類"]) assert.match(page, new RegExp(field));
  for (const category of ["餐飲", "日用品", "娛樂", "交通", "股票", "醫療"]) assert.match(page, new RegExp(category));
  assert.match(page, /"收入" : "支出"/);
  assert.doesNotMatch(page, /aria-label="通知"/);
  assert.doesNotMatch(page, /無法連接本機資料庫服務/);
  assert.match(page, /PDF 檔案/);
  assert.match(page, /匯出 PDF/);
  assert.match(page, /exports\/pdf/);
  assert.doesNotMatch(page, /CSV|台北富邦/);
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
