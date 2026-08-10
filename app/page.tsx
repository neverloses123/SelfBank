"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { isDuplicateTransaction } from "../lib/dedupe";

type Tx = { id: number; title: string; category: string; amount: number; date: string; type: "expense" | "income"; source: string };
type Recurring = { id: number; title: string; amount: number; day: number; category: string; active: boolean };

const seed: Tx[] = [
  { id: 1, title: "全聯福利中心", category: "日常採買", amount: 1286, date: "2026-08-10", type: "expense", source: "雲端發票" },
  { id: 2, title: "台灣高鐵", category: "交通", amount: 1490, date: "2026-08-09", type: "expense", source: "手動記帳" },
  { id: 3, title: "八月薪資", category: "收入", amount: 62000, date: "2026-08-08", type: "income", source: "銀行匯入" },
  { id: 4, title: "巷口咖啡", category: "餐飲", amount: 165, date: "2026-08-08", type: "expense", source: "雲端發票" },
  { id: 5, title: "中華電信", category: "帳單", amount: 899, date: "2026-08-07", type: "expense", source: "銀行匯入" },
  { id: 6, title: "誠品線上", category: "學習", amount: 780, date: "2026-08-06", type: "expense", source: "手動記帳" },
];

const categories = ["餐飲", "日常採買", "交通", "帳單", "娛樂", "學習", "醫療", "其他"];
const colors: Record<string, string> = { "日常採買": "#ff7a59", "交通": "#5b7cfa", "餐飲": "#ffc857", "帳單": "#37b899", "學習": "#9a72d5", "其他": "#a5adba" };
const money = (n: number) => new Intl.NumberFormat("zh-TW", { style: "currency", currency: "TWD", maximumFractionDigits: 0 }).format(n);
const pythonApiUrl = process.env.NEXT_PUBLIC_SELFBANK_API_URL || "";
const recurringSeed: Recurring[] = [
  { id: 101, title: "Netflix", amount: 390, day: 16, category: "娛樂", active: true },
  { id: 102, title: "手機月租", amount: 599, day: 20, category: "帳單", active: true },
  { id: 103, title: "YouTube Premium", amount: 199, day: 25, category: "娛樂", active: true },
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

export default function Home() {
  const [txs, setTxs] = useState<Tx[]>(seed);
  const [recurring, setRecurring] = useState<Recurring[]>(recurringSeed);
  const [modal, setModal] = useState<"add" | "carrier" | "import" | "recurring" | null>(null);
  const [toast, setToast] = useState("");
  const [filter, setFilter] = useState("全部");
  const [categoryFilter, setCategoryFilter] = useState("全部分類");
  const [barcode, setBarcode] = useState("/ABCD123");
  const [loaded, setLoaded] = useState(false);
  const [importType, setImportType] = useState<"csv" | "pdf">("csv");
  const [pdfBusy, setPdfBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const saved = localStorage.getItem("selfbank-v1-transactions");
    const savedCode = localStorage.getItem("selfbank-v1-barcode");
    const savedRecurring = localStorage.getItem("selfbank-v1-recurring");
    const timer = window.setTimeout(async () => {
      if (pythonApiUrl) {
        try {
          const [transactionsResponse, recurringResponse] = await Promise.all([
            fetch(`${pythonApiUrl}/transactions`), fetch(`${pythonApiUrl}/recurring`),
          ]);
          if (!transactionsResponse.ok || !recurringResponse.ok) throw new Error("API unavailable");
          setTxs(await transactionsResponse.json());
          setRecurring(await recurringResponse.json());
        } catch { setToast("無法連接本機資料庫服務"); }
      } else if (saved) { try { setTxs(JSON.parse(saved)); } catch { localStorage.removeItem("selfbank-v1-transactions"); } }
      if (savedCode) setBarcode(savedCode);
      if (!pythonApiUrl && savedRecurring) { try { setRecurring(JSON.parse(savedRecurring)); } catch { localStorage.removeItem("selfbank-v1-recurring"); } }
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
  const recurringTotal = activeRecurring.reduce((sum, item) => sum + item.amount, 0);

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

  function importCsv(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      if (pythonApiUrl) {
        const response = await fetch(`${pythonApiUrl}/imports/csv`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content: String(reader.result) }) });
        const result = await response.json();
        if (!response.ok) { setToast(result.detail || "CSV 匯入失敗"); return; }
        setTxs(prev => [...result.created, ...prev]); setModal(null);
        setToast(`已新增 ${result.created_count} 筆，略過 ${result.skipped_count} 筆重複消費`); setTimeout(() => setToast(""), 3500); return;
      }
      const lines = String(reader.result).split(/\r?\n/).slice(1).filter(Boolean);
      const parsed = lines.map((line, i) => {
        const [date, title, amount, type = "expense", category = "其他"] = line.split(",").map(v => v.trim());
        return { id: Date.now() + i, date, title, amount: Math.abs(Number(amount)), type: type === "income" ? "income" as const : "expense" as const, category, source: "CSV 匯入" };
      }).filter(t => t.date && t.title && Number.isFinite(t.amount));
      const accepted: Tx[] = [];
      let duplicateCount = 0;
      for (const candidate of parsed) {
        const duplicate = [...txs, ...accepted].some(existing => isDuplicateTransaction(candidate, existing));
        if (duplicate) duplicateCount += 1;
        else accepted.push(candidate);
      }
      setTxs(prev => [...accepted, ...prev]);
      setModal(null);
      setToast(`已新增 ${accepted.length} 筆，略過 ${duplicateCount} 筆重複消費`);
      setTimeout(() => setToast(""), 3500);
    };
    reader.readAsText(file);
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

  async function addRecurring(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const candidate = { title: String(fd.get("title")), amount: Number(fd.get("amount")), day: Number(fd.get("day")), category: String(fd.get("category")), active: true };
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
        <button className="nav active"><Icon name="home" />總覽</button>
        <button className="nav" onClick={() => document.getElementById("transactions")?.scrollIntoView({behavior:"smooth"})}><Icon name="list" />交易紀錄</button>
        <button className="nav" onClick={() => document.getElementById("budget")?.scrollIntoView({behavior:"smooth"})}><Icon name="budget" />預算規劃</button>
        <button className="nav" onClick={() => setModal("carrier")}><Icon name="card" />手機載具</button>
        <button className="nav" onClick={() => document.getElementById("recurring")?.scrollIntoView({behavior:"smooth"})}><Icon name="budget" />固定扣款</button>
        <button className="nav" onClick={() => setModal("import")}><Icon name="sync" />資料匯入</button>
      </nav>
      <div className="privacy"><span>●</span><div><b>{pythonApiUrl ? "已連接本機 SQL Server" : "資料僅存在此裝置"}</b><small>{pythonApiUrl ? "交易由本機 Python API 保存" : "SelfBank 不會上傳你的財務資料"}</small></div></div>
      <div className="profile"><div className="avatar">我</div><div><b>我的帳本</b><small>個人模式</small></div><button aria-label="更多選項">•••</button></div>
    </aside>

    <main>
      <header><div><p className="eyebrow">2026 年 8 月</p><h1>早安，今天也好好掌握生活。</h1></div><div className="header-actions"><button className="circle" aria-label="通知"><Icon name="bell" /></button><button className="primary" onClick={() => setModal("add")}><Icon name="plus" />新增交易</button></div></header>
      <section className="hero-card">
        <div><p>本月還可以安心使用</p><h2>{money(stats.balance)}</h2><span className="trend">↑ 較上月多 8.4%</span></div>
        <div className="hero-stats"><div><span>本月收入</span><b>{money(stats.income)}</b></div><div><span>本月支出</span><b>{money(stats.expense)}</b></div><div><span>儲蓄率</span><b>{stats.income ? Math.max(0, Math.round(stats.balance/stats.income*100)) : 0}%</b></div></div>
      </section>

      <section className="grid-top">
        <article className="panel spending"><div className="panel-head"><div><p className="eyebrow">支出分析</p><h3>錢都花去哪了？</h3></div><span>本月</span></div>
          <div className="spending-body"><div className="donut" style={{"--p": `${Math.min(75, stats.expense/100)}deg`} as React.CSSProperties}><div><strong>{money(stats.expense)}</strong><small>總支出</small></div></div>
            <div className="legend">{sortedCats.slice(0,4).map(([cat,val]) => <div key={cat}><i style={{background: colors[cat] || colors.其他}} /><span>{cat}</span><b>{money(val)}</b><small>{stats.expense ? Math.round(val/stats.expense*100) : 0}%</small></div>)}</div></div>
        </article>
        <article className="panel carrier"><div className="panel-head"><div><p className="eyebrow">快速出示</p><h3>手機載具</h3></div><span className="status">● 已儲存</span></div><div className="barcode" aria-label={`手機載具 ${barcode}`}><div className="bars">|||| ||| || |||| | ||| || ||||</div><strong>{barcode}</strong></div><p>結帳時出示條碼，發票同步功能待取得財政部正式授權後啟用。</p><button onClick={() => setModal("carrier")}>編輯我的載具</button></article>
      </section>

      <section className="grid-bottom">
        <article className="panel trend-card"><div className="panel-head"><div><p className="eyebrow">消費趨勢</p><h3>最近 7 天</h3></div><b>日均 {money(Math.round(stats.expense/7))}</b></div><div className="chart" aria-label="最近七天支出長條圖">{[42,72,35,88,55,28,64].map((h,i)=><div className="bar-col" key={i}><span className={i===3?"highlight":""} style={{height:`${h}%`}}></span><small>{["一","二","三","四","五","六","日"][i]}</small></div>)}</div></article>
        <article className="panel budget-card" id="budget"><div className="panel-head"><div><p className="eyebrow">本月預算</p><h3>守住生活的餘裕</h3></div><b>32%</b></div><div className="progress"><span style={{width:`${Math.min(100,stats.expense/15000*100)}%`}}></span></div><div className="budget-values"><span>已使用 <b>{money(stats.expense)}</b></span><span>預算 <b>{money(15000)}</b></span></div><p className="budget-note">照目前速度，月底預計可以剩下 {money(Math.max(0,15000-stats.expense))}。</p></article>
      </section>

      <section className="panel recurring-panel" id="recurring"><div className="panel-head"><div><p className="eyebrow">每月固定扣款</p><h3>先替未來的支出留位置</h3></div><button className="primary compact" onClick={() => setModal("recurring")}><Icon name="plus" />新增固定扣款</button></div>
        <div className="recurring-summary"><div><span>每月固定支出</span><strong>{money(recurringTotal)}</strong></div><div><span>啟用項目</span><strong>{activeRecurring.length} 筆</strong></div></div>
        <div className="recurring-list">{activeRecurring.map(item => <div className="recurring-item" key={item.id}><div className="recurring-logo">{item.title.slice(0,1)}</div><div><b>{item.title}</b><span>{item.category} · 每月 {item.day} 日</span></div><time>下次 {nextCharge(item.day)}</time><strong>{money(item.amount)}</strong><button aria-label={`停用 ${item.title}`} onClick={() => pauseRecurring(item)}>暫停</button></div>)}</div>
        <p className="recurring-hint">到期項目會列入預估；銀行 CSV 匯入後仍會使用防重複機制比對實際扣款。</p>
      </section>

      <section className="panel transactions" id="transactions"><div className="ledger-head"><div><p className="eyebrow">交易紀錄</p><h3>所有支出與收入</h3><span>共 {shown.length} 筆符合目前條件</span></div><button className="primary compact" onClick={() => setModal("add")}><Icon name="plus" />新增交易</button></div>
        <div className="ledger-controls" aria-label="交易篩選"><div className="filters" aria-label="收支類型">{[["全部收支","全部"],["只看支出","expense"],["只看收入","income"]].map(([label,value])=><button key={value} className={filter===value?"selected":""} aria-pressed={filter===value} onClick={()=>setFilter(value)}>{label}</button>)}</div><label>分類<select aria-label="交易分類" value={categoryFilter} onChange={event => setCategoryFilter(event.target.value)}><option>全部分類</option>{transactionCategories.map(category => <option key={category}>{category}</option>)}</select></label></div>
        <div className="ledger-summary"><div><span>篩選後收入</span><strong className="income">+{money(shownSummary.income)}</strong></div><div><span>篩選後支出</span><strong>−{money(shownSummary.expense)}</strong></div><div><span>收支差額</span><strong className={shownSummary.net >= 0 ? "income" : ""}>{shownSummary.net >= 0 ? "+" : "−"}{money(Math.abs(shownSummary.net))}</strong></div></div>
        <div className="tx-list" aria-live="polite">{shown.length ? shown.map(t=><div className="tx" key={t.id}><div className={`tx-icon ${t.type}`}>{t.type === "income" ? "↙" : t.category.slice(0,1)}</div><div className="tx-title"><b>{t.title}</b><span>{t.category} · {t.source}</span></div><time dateTime={t.date}>{t.date.replaceAll("-","/")}</time><strong className={t.type}>{t.type === "income" ? "+" : "−"}{money(t.amount)}</strong></div>) : <div className="empty-ledger"><b>沒有符合條件的交易</b><span>請調整收支類型或分類篩選。</span></div>}</div>
      </section>
      <footer>SelfBank v1 · 個人財務資料，安心留在自己的裝置</footer>
    </main>

    {modal && <div className="overlay"><button className="backdrop" onClick={()=>setModal(null)} aria-label="關閉視窗" /><div className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><button className="modal-close" onClick={()=>setModal(null)} aria-label="關閉"><Icon name="close" /></button>
      {modal === "add" && <><p className="eyebrow">快速記一筆</p><h2 id="modal-title">新增交易</h2><form onSubmit={addTx}><label>類型<select name="type" defaultValue="expense"><option value="expense">支出</option><option value="income">收入</option></select></label><label>名稱<input name="title" required placeholder="例如：午餐" /></label><div className="form-row"><label>金額<input name="amount" type="number" min="1" required placeholder="0" /></label><label>日期<input name="date" type="date" required defaultValue="2026-08-10" /></label></div><label>分類<select name="category">{categories.map(c=><option key={c}>{c}</option>)}</select></label><button className="primary submit" type="submit">儲存交易</button></form></>}
      {modal === "carrier" && <><p className="eyebrow">快速出示</p><h2 id="modal-title">設定手機載具</h2><p className="modal-copy">請輸入財政部核發、以「/」開頭的 8 碼手機條碼。條碼只會保存在這個瀏覽器。</p><form onSubmit={e=>{e.preventDefault(); const code=String(new FormData(e.currentTarget).get("barcode")).toUpperCase(); setBarcode(code); localStorage.setItem("selfbank-v1-barcode",code); setModal(null);setToast("載具已更新");setTimeout(()=>setToast(""),2500)}}><label>手機條碼<input name="barcode" required pattern="/[0-9A-Z.+\-]{7}" maxLength={8} defaultValue={barcode} /></label><button className="primary submit">儲存載具</button></form></>}
      {modal === "import" && <><p className="eyebrow">資料匯入</p><h2 id="modal-title">匯入銀行紀錄</h2><div className="import-tabs"><button className={importType === "csv" ? "selected" : ""} onClick={() => setImportType("csv")}>CSV</button><button className={importType === "pdf" ? "selected" : ""} onClick={() => setImportType("pdf")}>加密 PDF</button></div><div className="dedupe-note"><b>✓ 防重複記帳已開啟</b><span>會比對金額、店家與三日內的載具消費。</span></div>{importType === "csv" ? <><p className="modal-copy">欄位順序：日期、名稱、金額、類型、分類；類型請填 expense 或 income。</p><button className="dropzone" onClick={()=>fileRef.current?.click()}><Icon name="upload" /><b>選擇 CSV 檔案</b><span>資料會在你的裝置中處理</span></button><input ref={fileRef} className="hidden" type="file" accept=".csv,text/csv" onChange={importCsv}/></> : <form onSubmit={importPdf}><label>銀行 PDF<input name="pdf" type="file" accept=".pdf,application/pdf" required /></label><label>PDF 開啟密碼<input name="password" type="password" required autoComplete="off" placeholder="每次匯入時輸入" /></label><p className="modal-copy secure-copy">密碼只用於本次解密，不會寫入設定檔、資料庫或操作紀錄。</p>{!pythonApiUrl && <p className="api-warning">請先啟動 Python API 並設定 NEXT_PUBLIC_SELFBANK_API_URL，才能使用 PDF 匯入。</p>}<button className="primary submit" type="submit" disabled={!pythonApiUrl || pdfBusy}>{pdfBusy ? "解密與比對中…" : "匯入並比對重複消費"}</button></form>}</>}
      {modal === "recurring" && <><p className="eyebrow">每月固定扣款</p><h2 id="modal-title">新增固定支出</h2><form onSubmit={addRecurring}><label>名稱<input name="title" required placeholder="例如：網路費或訂閱服務" /></label><div className="form-row"><label>每月金額<input name="amount" type="number" min="1" required placeholder="0" /></label><label>每月扣款日<input name="day" type="number" min="1" max="28" required placeholder="例如：15" /></label></div><label>分類<select name="category">{categories.map(c=><option key={c}>{c}</option>)}</select></label><p className="modal-copy">選擇 1–28 日可避免短月份日期不存在；之後匯入銀行紀錄時會自動比對，避免重複記帳。</p><button className="primary submit" type="submit">加入固定扣款</button></form></>}
    </div></div>}
    {toast && <div className="toast">✓ {toast}</div>}
  </div>;
}
