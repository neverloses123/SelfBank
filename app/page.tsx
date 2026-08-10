"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type Tx = { id: number; title: string; category: string; amount: number; date: string; type: "expense" | "income"; source: string; transaction_time?: string | null; summary?: string | null; expense_amount?: number | null; income_amount?: number | null; balance?: number | null; note?: string | null };
type Recurring = { id: number; title: string; amount: number; day: number; category: string; type: "expense" | "income"; active: boolean };

const seed: Tx[] = [
  { id: 1, title: "全聯福利中心", category: "日常採買", amount: 1286, date: "2026-08-10", type: "expense", source: "手動記帳" },
  { id: 2, title: "台灣高鐵", category: "交通", amount: 1490, date: "2026-08-09", type: "expense", source: "手動記帳" },
  { id: 3, title: "八月薪資", category: "收入", amount: 62000, date: "2026-08-08", type: "income", source: "銀行匯入" },
  { id: 4, title: "巷口咖啡", category: "餐飲", amount: 165, date: "2026-08-08", type: "expense", source: "手動記帳" },
  { id: 5, title: "中華電信", category: "帳單", amount: 899, date: "2026-08-07", type: "expense", source: "銀行匯入" },
  { id: 6, title: "誠品線上", category: "學習", amount: 780, date: "2026-08-06", type: "expense", source: "手動記帳" },
];

const categories = ["餐飲", "日常採買", "交通", "帳單", "娛樂", "學習", "醫療", "其他"];
const colors: Record<string, string> = { "日常採買": "#ff7a59", "交通": "#5b7cfa", "餐飲": "#ffc857", "帳單": "#37b899", "學習": "#9a72d5", "其他": "#a5adba" };
const money = (n: number) => new Intl.NumberFormat("zh-TW", { style: "currency", currency: "TWD", maximumFractionDigits: 0 }).format(n);
const pythonApiUrl = process.env.NEXT_PUBLIC_SELFBANK_API_URL || "";
const recurringSeed: Recurring[] = [
  { id: 100, title: "每月薪資", amount: 62000, day: 8, category: "收入", type: "income", active: true },
  { id: 101, title: "Netflix", amount: 390, day: 16, category: "娛樂", type: "expense", active: true },
  { id: 102, title: "手機月租", amount: 599, day: 20, category: "帳單", type: "expense", active: true },
  { id: 103, title: "YouTube Premium", amount: 199, day: 25, category: "娛樂", type: "expense", active: true },
];

function nextCharge(day: number) {
  const today = new Date();
  const target = new Date(today.getFullYear(), today.getMonth() + (today.getDate() > day ? 1 : 0), day);
  return `${target.getMonth() + 1}/${target.getDate()}`;
}

function Icon({ name }: { name: string }) {
  const icons: Record<string, string> = { home: "⌂", list: "≡", budget: "◎", card: "▰", sync: "↻", plus: "+", bell: "◌", upload: "⇧", close: "×" };
  return <span className="icon" aria-hidden="true">{icons[name]}</span>;
}

export function SelfBankApp({ view = "transactions" }: { view?: "transactions" | "recurring" | "analysis" }) {
  const [txs, setTxs] = useState<Tx[]>(seed);
  const [recurring, setRecurring] = useState<Recurring[]>(recurringSeed);
  const [modal, setModal] = useState<"add" | "import" | "recurring" | null>(null);
  const [toast, setToast] = useState("");
  const [filter, setFilter] = useState("全部");
  const [categoryFilter, setCategoryFilter] = useState("全部分類");
  const [recurringFilter, setRecurringFilter] = useState<"all" | "expense" | "income">("all");
  const [loaded, setLoaded] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("selfbank-v1-transactions");
    const savedRecurring = localStorage.getItem("selfbank-v1-recurring");
    const timer = window.setTimeout(async () => {
      if (pythonApiUrl) {
        try {
          const [transactionsResponse, recurringResponse] = await Promise.all([
            fetch(`${pythonApiUrl}/transactions`), fetch(`${pythonApiUrl}/recurring`),
          ]);
          if (!transactionsResponse.ok || !recurringResponse.ok) throw new Error("API unavailable");
          setTxs(await transactionsResponse.json());
          setRecurring((await recurringResponse.json()).map((item: Recurring) => ({ ...item, type: item.type || "expense" })));
        } catch { setToast("無法連接本機資料庫服務"); }
      } else if (saved) { try { setTxs(JSON.parse(saved)); } catch { localStorage.removeItem("selfbank-v1-transactions"); } }
      if (!pythonApiUrl && savedRecurring) { try { setRecurring(JSON.parse(savedRecurring).map((item: Recurring) => ({ ...item, type: item.type || "expense" }))); } catch { localStorage.removeItem("selfbank-v1-recurring"); } }
      setLoaded(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);
  useEffect(() => { if (loaded && !pythonApiUrl) localStorage.setItem("selfbank-v1-transactions", JSON.stringify(txs)); }, [txs, loaded]);
  useEffect(() => { if (loaded && !pythonApiUrl) localStorage.setItem("selfbank-v1-recurring", JSON.stringify(recurring)); }, [recurring, loaded]);

  const stats = useMemo(() => {
    const income = txs.filter(t => t.type === "income").reduce((s, t) => s + t.amount, 0);
    const expense = txs.filter(t => t.type === "expense").reduce((s, t) => s + t.amount, 0);
    return { income, expense, balance: income - expense };
  }, [txs]);
  const catTotals = useMemo(() => txs.filter(t => t.type === "expense").reduce<Record<string, number>>((a, t) => ({ ...a, [t.category]: (a[t.category] || 0) + t.amount }), {}), [txs]);
  const sortedCats = Object.entries(catTotals).sort((a,b) => b[1]-a[1]);
  const transactionCategories = useMemo(() => Array.from(new Set(txs.map(t => t.category))).sort((a, b) => a.localeCompare(b, "zh-TW")), [txs]);
  const shown = useMemo(() => txs.filter(t => (filter === "全部" || t.type === filter) && (categoryFilter === "全部分類" || t.category === categoryFilter)), [txs, filter, categoryFilter]);
  const shownSummary = useMemo(() => {
    const income = shown.filter(t => t.type === "income").reduce((sum, item) => sum + item.amount, 0);
    const expense = shown.filter(t => t.type === "expense").reduce((sum, item) => sum + item.amount, 0);
    return { income, expense, net: income - expense };
  }, [shown]);
  const activeRecurring = recurring.filter(item => item.active).sort((a, b) => a.day - b.day);
  const visibleRecurring = activeRecurring.filter(item => recurringFilter === "all" || item.type === recurringFilter);
  const recurringExpenseTotal = activeRecurring.filter(item => item.type === "expense").reduce((sum, item) => sum + item.amount, 0);
  const recurringIncomeTotal = activeRecurring.filter(item => item.type === "income").reduce((sum, item) => sum + item.amount, 0);
  const topExpenseCategory = sortedCats[0];
  const projectedExpense = stats.expense + recurringExpenseTotal;
  const variableShare = projectedExpense ? Math.round(stats.expense / projectedExpense * 100) : 0;
  const pageMeta = {
    transactions: ["交易紀錄", "查看、分類並管理所有收入與支出。"],
    recurring: ["固定收支", "安排每月固定收入與固定支出。"],
    analysis: ["財務分析", "看懂趨勢、盈虧、儲蓄率與本月異常。"],
  }[view];

  async function addTx(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const type = fd.get("type") as "expense" | "income";
    const candidate = { title: String(fd.get("title")), category: type === "income" ? "收入" : String(fd.get("category")), amount: Number(fd.get("amount")), date: String(fd.get("date")), type, source: "手動記帳" };
    let created: Tx = { id: Date.now(), ...candidate };
    if (pythonApiUrl) {
      const response = await fetch(`${pythonApiUrl}/transactions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(candidate) });
      if (!response.ok) { setToast("資料庫寫入失敗"); return; }
      created = await response.json();
    }
    setTxs([created, ...txs]);
    setModal(null); setToast("交易已新增"); setTimeout(() => setToast(""), 2500);
  }

  async function importPdf(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    const file = fd.get("pdf") as File;
    const password = String(fd.get("password") || "");
    if (!pythonApiUrl || !file || !password) return;
    setPdfBusy(true);
    try {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(new Error("無法讀取 PDF"));
        reader.readAsDataURL(file);
      });
      const response = await fetch(`${pythonApiUrl}/imports/pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: file.name, content_base64: dataUrl.split(",")[1], password }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "PDF 匯入失敗");
      setTxs(prev => [...result.created.map((item: Tx) => ({ ...item, id: Number(item.id) })), ...prev]);
      form.reset();
      setModal(null);
      setToast(`已新增 ${result.created_count} 筆，略過 ${result.skipped_count} 筆重複消費`);
      setTimeout(() => setToast(""), 3500);
    } catch (error) {
      setToast(error instanceof Error ? error.message : "PDF 匯入失敗");
      setTimeout(() => setToast(""), 3500);
    } finally {
      setPdfBusy(false);
    }
  }

  async function exportPdf() {
    if (!pythonApiUrl) { setToast("請先啟動本機 Python API，才能匯出 PDF"); setTimeout(() => setToast(""), 3000); return; }
    try {
      const response = await fetch(`${pythonApiUrl}/exports/pdf`);
      if (!response.ok) throw new Error("PDF 匯出失敗");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = `SelfBank-交易紀錄-${new Date().toISOString().slice(0, 10)}.pdf`;
      document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
      setToast("交易紀錄 PDF 已匯出"); setTimeout(() => setToast(""), 2500);
    } catch { setToast("PDF 匯出失敗，請確認本機 API 已啟動"); setTimeout(() => setToast(""), 3000); }
  }

  async function addRecurring(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const type = fd.get("type") as "expense" | "income";
    const candidate = { title: String(fd.get("title")), amount: Number(fd.get("amount")), day: Number(fd.get("day")), category: type === "income" ? "收入" : String(fd.get("category")), type, active: true };
    let created: Recurring = { id: Date.now(), ...candidate };
    if (pythonApiUrl) {
      const response = await fetch(`${pythonApiUrl}/recurring`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(candidate) });
      if (!response.ok) { setToast("資料庫寫入失敗"); return; }
      created = await response.json();
    }
    setRecurring(prev => [...prev, created]);
    setModal(null); setToast("固定扣款已加入"); setTimeout(() => setToast(""), 2500);
  }

  async function pauseRecurring(item: Recurring) {
    if (pythonApiUrl) {
      const response = await fetch(`${pythonApiUrl}/recurring/${item.id}?active=false`, { method: "PATCH" });
      if (!response.ok) { setToast("資料庫更新失敗"); return; }
    }
    setRecurring(prev => prev.map(row => row.id === item.id ? {...row, active:false} : row));
  }

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">S</span><span>SelfBank</span></div>
      <nav aria-label="主要選單">
        <a className={`nav ${view === "transactions" ? "active" : ""}`} href="/"><Icon name="list" />交易紀錄</a>
        <a className={`nav ${view === "recurring" ? "active" : ""}`} href="/recurring"><Icon name="budget" />固定收支</a>
        <a className={`nav ${view === "analysis" ? "active" : ""}`} href="/analysis"><Icon name="home" />財務分析</a>
        <button className="nav" onClick={() => setModal("import")}><Icon name="sync" />資料匯入</button>
      </nav>
      <div className="privacy"><span>●</span><div><b>{pythonApiUrl ? "已連接本機 SQL Server" : "資料僅存在此裝置"}</b><small>{pythonApiUrl ? "交易由本機 Python API 保存" : "SelfBank 不會上傳你的財務資料"}</small></div></div>
      <div className="profile"><div className="avatar">我</div><div><b>我的帳本</b><small>個人模式</small></div><button aria-label="更多選項">•••</button></div>
    </aside>

    <main>
      <header><div><p className="eyebrow">SelfBank · 2026 年 8 月</p><h1>{pageMeta[0]}</h1><p className="page-description">{pageMeta[1]}</p></div><div className="header-actions"><button className="circle" aria-label="通知"><Icon name="bell" /></button>{view === "transactions" && <button className="primary" onClick={() => setModal("add")}><Icon name="plus" />新增交易</button>}{view === "recurring" && <button className="primary" onClick={() => setModal("recurring")}><Icon name="plus" />新增固定收支</button>}</div></header>
      {view === "analysis" && <>
      <section className="anomaly-panel"><div className="anomaly-title"><span>⚠</span><div><p className="eyebrow">主動偵測</p><h2>本月財務異常</h2></div></div><div className="anomaly-grid"><div><b>{topExpenseCategory?.[0] || "尚無支出"}支出 {money(topExpenseCategory?.[1] || 0)}</b><span>{topExpenseCategory ? "目前為本月最高支出分類" : "新增交易後開始分析"}</span></div><div><b>可變支出占預估總支出 {variableShare}%</b><span>{variableShare >= 70 ? "占比偏高，建議檢查非固定消費" : "目前仍在可控範圍"}</span></div><div><b>預估月底總支出 {money(projectedExpense)}</b><span>包含目前支出與尚未入帳的固定支出</span></div><div><b>近 6 個月比較：資料累積中</b><span>資料滿 6 個月後啟用平均、次數與連續上升警示</span></div></div></section>
      <section className="hero-card">
        <div><p>本月盈虧</p><h2>{money(stats.balance)}</h2><span className="trend">收入減去支出</span></div>
        <div className="hero-stats"><div><span>本月收入</span><b>{money(stats.income)}</b></div><div><span>本月支出</span><b>{money(stats.expense)}</b></div><div><span>儲蓄率</span><b>{stats.income ? Math.max(0, Math.round(stats.balance/stats.income*100)) : 0}%</b></div></div>
      </section>

      <section className="grid-top analysis-grid">
        <article className="panel spending"><div className="panel-head"><div><p className="eyebrow">支出分析</p><h3>錢都花去哪了？</h3></div><span>本月</span></div>
          <div className="spending-body"><div className="donut" style={{"--p": `${Math.min(75, stats.expense/100)}deg`} as React.CSSProperties}><div><strong>{money(stats.expense)}</strong><small>總支出</small></div></div>
            <div className="legend">{sortedCats.slice(0,4).map(([cat,val]) => <div key={cat}><i style={{background: colors[cat] || colors.其他}} /><span>{cat}</span><b>{money(val)}</b><small>{stats.expense ? Math.round(val/stats.expense*100) : 0}%</small></div>)}</div></div>
        </article>
      </section>

      <section className="grid-bottom">
        <article className="panel trend-card"><div className="panel-head"><div><p className="eyebrow">消費趨勢</p><h3>最近 7 天</h3></div><b>日均 {money(Math.round(stats.expense/7))}</b></div><div className="chart" aria-label="最近七天支出長條圖">{[42,72,35,88,55,28,64].map((h,i)=><div className="bar-col" key={i}><span className={i===3?"highlight":""} style={{height:`${h}%`}}></span><small>{["一","二","三","四","五","六","日"][i]}</small></div>)}</div></article>
        <article className="panel cost-structure"><div className="panel-head"><div><p className="eyebrow">支出結構</p><h3>固定與可變支出</h3></div><b>{money(projectedExpense)}</b></div><div className="cost-table"><div><span>固定支出</span><b>{money(recurringExpenseTotal)}</b><small>{projectedExpense ? Math.round(recurringExpenseTotal/projectedExpense*100) : 0}%</small></div><div><span>可變支出</span><b>{money(stats.expense)}</b><small>{variableShare}%</small></div><div className="total"><span>預估總支出</span><b>{money(projectedExpense)}</b><small>100%</small></div></div></article>
      </section>
      </>}

      {view === "recurring" && <section className="panel recurring-panel page-panel" id="recurring"><div className="panel-head"><div><p className="eyebrow">每月固定收支</p><h3>收入與支出都先安排好</h3></div><button className="primary compact" onClick={() => setModal("recurring")}><Icon name="plus" />新增固定收支</button></div>
        <div className="recurring-summary"><div className="income-card"><span>每月固定收入</span><strong>{money(recurringIncomeTotal)}</strong></div><div><span>每月固定支出</span><strong>{money(recurringExpenseTotal)}</strong></div><div><span>預估淨收入</span><strong>{money(recurringIncomeTotal - recurringExpenseTotal)}</strong></div></div>
        <div className="recurring-tabs filters" aria-label="固定收支篩選">{[["全部","all"],["固定支出","expense"],["固定收入","income"]].map(([label,value]) => <button key={value} aria-pressed={recurringFilter === value} className={recurringFilter === value ? "selected" : ""} onClick={() => setRecurringFilter(value as "all" | "expense" | "income")}>{label}</button>)}</div>
        <div className="recurring-list">{visibleRecurring.map(item => <div className={`recurring-item ${item.type}`} key={item.id}><div className="recurring-logo">{item.type === "income" ? "+" : "−"}</div><div><b>{item.title}</b><span>{item.type === "income" ? "固定收入" : "固定支出"} · {item.category} · 每月 {item.day} 日</span></div><time>下次 {nextCharge(item.day)}</time><strong>{item.type === "income" ? "+" : "−"}{money(item.amount)}</strong><button aria-label={`停用 ${item.title}`} onClick={() => pauseRecurring(item)}>暫停</button></div>)}</div>
        <p className="recurring-hint">固定收支用於預估；匯入銀行紀錄時仍會套用防重複規則，以實際入帳為準。</p>
      </section>}

      {view === "transactions" && <section className="panel transactions page-panel" id="transactions"><div className="ledger-head"><div><p className="eyebrow">交易紀錄</p><h3>所有支出與收入</h3><span>共 {shown.length} 筆符合目前條件</span></div><div className="ledger-actions"><button className="secondary compact" onClick={exportPdf} aria-label="匯出交易紀錄 PDF"><span aria-hidden="true">⇩</span>匯出 PDF</button><button className="primary compact" onClick={() => setModal("add")}><Icon name="plus" />新增交易</button></div></div>
        <div className="ledger-controls" aria-label="交易篩選"><div className="filters" aria-label="收支類型">{[["全部收支","全部"],["只看支出","expense"],["只看收入","income"]].map(([label,value])=><button key={value} className={filter===value?"selected":""} aria-pressed={filter===value} onClick={()=>setFilter(value)}>{label}</button>)}</div><label>分類<select aria-label="交易分類" value={categoryFilter} onChange={event => setCategoryFilter(event.target.value)}><option>全部分類</option>{transactionCategories.map(category => <option key={category}>{category}</option>)}</select></label></div>
        <div className="ledger-summary"><div><span>篩選後收入</span><strong className="income">+{money(shownSummary.income)}</strong></div><div><span>篩選後支出</span><strong>−{money(shownSummary.expense)}</strong></div><div><span>收支差額</span><strong className={shownSummary.net >= 0 ? "income" : ""}>{shownSummary.net >= 0 ? "+" : "−"}{money(Math.abs(shownSummary.net))}</strong></div></div>
        <div className="bank-table-wrap" aria-live="polite">{shown.length ? <table className="bank-table"><thead><tr><th>帳務日期</th><th>交易時間</th><th>摘要</th><th>支出金額</th><th>存入金額</th><th>即時餘額</th><th>附註</th></tr></thead><tbody>{shown.map(t=><tr key={t.id}><td><time dateTime={t.date}>{t.date.replaceAll("-","/")}</time></td><td>{t.transaction_time || "—"}</td><td><b>{t.summary || t.title}</b><small>{t.category} · {t.source}</small></td><td className="expense-cell">{t.type === "expense" ? money(t.expense_amount ?? t.amount) : "—"}</td><td className="income-cell">{t.type === "income" ? money(t.income_amount ?? t.amount) : "—"}</td><td>{t.balance == null ? "—" : money(t.balance)}</td><td>{t.note || (t.summary ? t.title : "—")}</td></tr>)}</tbody></table> : <div className="empty-ledger"><b>沒有符合條件的交易</b><span>請調整收支類型或分類篩選。</span></div>}</div>
      </section>}
      <footer>SelfBank v1 · 個人財務資料，安心留在自己的裝置</footer>
    </main>

    {modal && <div className="overlay"><button className="backdrop" onClick={()=>setModal(null)} aria-label="關閉視窗" /><div className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><button className="modal-close" onClick={()=>setModal(null)} aria-label="關閉"><Icon name="close" /></button>
      {modal === "add" && <><p className="eyebrow">快速記一筆</p><h2 id="modal-title">新增交易</h2><form onSubmit={addTx}><label>類型<select name="type" defaultValue="expense"><option value="expense">支出</option><option value="income">收入</option></select></label><label>名稱<input name="title" required placeholder="例如：午餐" /></label><div className="form-row"><label>金額<input name="amount" type="number" min="1" required placeholder="0" /></label><label>日期<input name="date" type="date" required defaultValue="2026-08-10" /></label></div><label>分類<select name="category">{categories.map(c=><option key={c}>{c}</option>)}</select></label><button className="primary submit" type="submit">儲存交易</button></form></>}
      {modal === "import" && <><p className="eyebrow">PDF 匯入</p><h2 id="modal-title">匯入交易紀錄</h2><div className="dedupe-note"><b>✓ 防重複記帳已開啟</b><span>會比對日期、金額與交易內容，已匯入的紀錄不會重複新增。</span></div><form onSubmit={importPdf}><label>PDF 檔案<input name="pdf" type="file" accept=".pdf,application/pdf" required /></label><label>PDF 開啟密碼<input name="password" type="password" required autoComplete="off" placeholder="每次匯入時輸入" /></label><p className="modal-copy secure-copy">匯入後會顯示帳務日期、交易時間、摘要、支出金額、存入金額、即時餘額與附註。密碼只用於本次解密，不會保存。</p>{!pythonApiUrl && <p className="api-warning">請先啟動本機 Python API，才能解密 PDF 並寫入你的 SQL Server。</p>}<button className="primary submit" type="submit" disabled={!pythonApiUrl || pdfBusy}>{pdfBusy ? "解密與匯入中…" : "匯入 PDF"}</button></form></>}
      {modal === "recurring" && <><p className="eyebrow">每月固定收支</p><h2 id="modal-title">新增固定收入或支出</h2><form onSubmit={addRecurring}><label>類型<select name="type" defaultValue="expense"><option value="expense">固定支出</option><option value="income">固定收入</option></select></label><label>名稱<input name="title" required placeholder="例如：薪資、房租或訂閱服務" /></label><div className="form-row"><label>每月金額<input name="amount" type="number" min="1" required placeholder="0" /></label><label>每月入帳／扣款日<input name="day" type="number" min="1" max="28" required placeholder="例如：15" /></label></div><label>分類<select name="category">{categories.map(c=><option key={c}>{c}</option>)}</select></label><p className="modal-copy">固定收入會自動歸類為收入；選擇 1–28 日可避免短月份日期不存在。</p><button className="primary submit" type="submit">加入固定收支</button></form></>}
    </div></div>}
    {toast && <div className="toast">✓ {toast}</div>}
  </div>;
}

export default function Home() {
  return <SelfBankApp view="transactions" />;
}
