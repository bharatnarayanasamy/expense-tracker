import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  categorizeUnknowns,
  exportTsvUrl,
  exportXlsxUrl,
  fetchCategories,
  fetchInsights,
  fetchTransactions,
  patchCategory,
  uploadPdf,
  type Insights,
  type Transaction,
  type UploadResult,
} from "./api";

type Tab = "upload" | "transactions" | "insights";

function formatMoney(n: number) {
  return n.toLocaleString(undefined, { style: "currency", currency: "USD" });
}

export default function App() {
  const [tab, setTab] = useState<Tab>("upload");
  const [categories, setCategories] = useState<string[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [insights, setInsights] = useState<Insights | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadNotes, setUploadNotes] = useState<UploadResult[]>([]);
  const [drag, setDrag] = useState(false);

  const [bank, setBank] = useState("");
  const [category, setCategory] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const filterParams = useMemo(() => {
    const p: Record<string, string> = {};
    if (bank) p.bank = bank;
    if (category) p.category = category;
    if (dateFrom) p.date_from = dateFrom;
    if (dateTo) p.date_to = dateTo;
    return p;
  }, [bank, category, dateFrom, dateTo]);

  const refresh = useCallback(async () => {
    setError(null);
    const [cats, txns, ins] = await Promise.all([
      fetchCategories(),
      fetchTransactions(filterParams),
      fetchInsights(),
    ]);
    setCategories(cats.categories);
    setTransactions(txns.transactions);
    setInsights(ins);
  }, [filterParams]);

  useEffect(() => {
    refresh().catch((e: Error) => setError(e.message));
  }, [refresh]);

  const banks = useMemo(
    () => [...new Set(transactions.map((t) => t.bank))].sort(),
    [transactions],
  );

  const monthChartData = useMemo(() => {
    if (!insights) return [];
    return insights.by_month.map((m) => ({
      month: m.month,
      spend: Math.round((m.spend || 0) * 100) / 100,
      income: Math.round((m.income || 0) * 100) / 100,
    }));
  }, [insights]);

  const categoryMonthChart = useMemo(() => {
    if (!insights) return { data: [] as Record<string, string | number>[], keys: [] as string[] };
    const months = [...new Set(insights.by_month_category.map((r) => r.month))].sort();
    const cats = [...new Set(insights.by_month_category.map((r) => r.category))].slice(0, 6);
    const data = months.map((month) => {
      const row: Record<string, string | number> = { month };
      for (const c of cats) {
        const found = insights.by_month_category.find(
          (r) => r.month === month && r.category === c,
        );
        row[c] = found ? Math.round(found.spend * 100) / 100 : 0;
      }
      return row;
    });
    return { data, keys: cats };
  }, [insights]);

  async function handleFiles(files: FileList | null) {
    if (!files?.length) return;
    setLoading(true);
    setError(null);
    const results: UploadResult[] = [];
    try {
      for (const file of Array.from(files)) {
        if (!file.name.toLowerCase().endsWith(".pdf")) {
          throw new Error(`${file.name} is not a PDF.`);
        }
        results.push(await uploadPdf(file));
      }
      setUploadNotes((prev) => [...results, ...prev].slice(0, 10));
      await refresh();
      setTab("transactions");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  async function copyForExcel() {
    const res = await fetch(exportTsvUrl(filterParams));
    const tsv = await res.text();
    await navigator.clipboard.writeText(tsv);
  }

  async function onCategoryChange(id: number, next: string) {
    await patchCategory(id, next);
    await refresh();
  }

  async function onLlmUnknowns() {
    setLoading(true);
    try {
      const r = await categorizeUnknowns();
      setUploadNotes((prev) => [
        {
          upload_id: 0,
          bank: "LLM",
          parsed_count: r.updated,
          inserted: r.updated,
          skipped_duplicates: 0,
          warnings: r.updated ? [] : ["No updates (no API key or no unknowns)."],
        },
        ...prev,
      ]);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "LLM categorization failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <header>
        <div>
          <h1>Expense Tracker</h1>
          <p className="subtitle">PDF statements → categories → insights (local only)</p>
        </div>
        <nav className="tabs">
          {(["upload", "transactions", "insights"] as Tab[]).map((t) => (
            <button
              key={t}
              type="button"
              className={`tab ${tab === t ? "active" : ""}`}
              onClick={() => setTab(t)}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </nav>
      </header>

      {error && (
        <div className="warnings" role="alert">
          {error}
        </div>
      )}

      {tab === "upload" && (
        <section className="panel">
          <div
            className={`dropzone ${drag ? "drag" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              void handleFiles(e.dataTransfer.files);
            }}
          >
            <p>
              <strong>Drop PDF bank statements</strong> or choose files
            </p>
            <p className="muted">Chase, Bank of America, Wells Fargo, Capital One + generic fallback</p>
            <p style={{ marginTop: "1rem" }}>
              <label className="btn">
                Choose PDFs
                <input
                  type="file"
                  accept="application/pdf,.pdf"
                  multiple
                  hidden
                  onChange={(e) => void handleFiles(e.target.files)}
                />
              </label>
            </p>
          </div>
          <div className="actions" style={{ marginTop: "1rem" }}>
            <button type="button" className="btn secondary" disabled={loading} onClick={() => void onLlmUnknowns()}>
              Categorize unknowns (LLM)
            </button>
            <span className="muted">Requires ANTHROPIC_API_KEY in your environment</span>
          </div>
          {loading && <p className="muted">Processing…</p>}
          {uploadNotes.length > 0 && (
            <div className="upload-results">
              {uploadNotes.map((u, i) => (
                <div key={`${u.upload_id}-${i}`} className="kpi">
                  <label>
                    {u.bank} — {u.inserted} new, {u.skipped_duplicates} duplicates skipped
                  </label>
                  {u.warnings.length > 0 && (
                    <ul className="muted">
                      {u.warnings.map((w) => (
                        <li key={w}>{w}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {tab === "transactions" && (
        <section className="panel">
          <div className="filters">
            <select value={bank} onChange={(e) => setBank(e.target.value)}>
              <option value="">All banks</option>
              {banks.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          <div className="actions">
            <button type="button" className="btn secondary" onClick={() => void copyForExcel()}>
              Copy for Excel
            </button>
            <a className="btn secondary" href={exportXlsxUrl(filterParams)} style={{ textDecoration: "none" }}>
              Download .xlsx
            </a>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Description</th>
                  <th>Amount</th>
                  <th>Category</th>
                  <th>Bank</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((t) => (
                  <tr key={t.id}>
                    <td>{t.posted_date}</td>
                    <td>{t.description}</td>
                    <td className={`amount ${t.amount < 0 ? "neg" : "pos"}`}>{formatMoney(t.amount)}</td>
                    <td>
                      <select
                        value={t.category}
                        onChange={(e) => void onCategoryChange(t.id, e.target.value)}
                      >
                        {categories.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>{t.bank}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!transactions.length && <p className="muted">No transactions yet — upload a PDF.</p>}
        </section>
      )}

      {tab === "insights" && insights && (
        <section className="panel">
          <div className="kpi-grid">
            <div className="kpi">
              <label>Total spend</label>
              <strong>{formatMoney(insights.total_spend)}</strong>
            </div>
            <div className="kpi">
              <label>Top category</label>
              <strong>
                {insights.top_category ?? "—"} ({formatMoney(insights.top_category_spend)})
              </strong>
            </div>
            <div className="kpi">
              <label>Latest month</label>
              <strong>
                {insights.latest_month ?? "—"} · {formatMoney(insights.latest_month_spend)}
              </strong>
            </div>
            <div className="kpi">
              <label>Month vs prior</label>
              <strong>
                {insights.month_over_month_delta_pct === null
                  ? "—"
                  : `${insights.month_over_month_delta_pct > 0 ? "+" : ""}${insights.month_over_month_delta_pct}%`}
              </strong>
            </div>
          </div>

          <div className="chart-block">
            <h3>Spend & income by month</h3>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={monthChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e0d8cc" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip formatter={(v: number) => formatMoney(v)} />
                <Legend />
                <Bar dataKey="spend" fill="#c45c26" name="Spend" />
                <Bar dataKey="income" fill="#2d6a4f" name="Income" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {categoryMonthChart.keys.length > 0 && (
            <div className="chart-block">
              <h3>Top categories by month</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={categoryMonthChart.data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e0d8cc" />
                  <XAxis dataKey="month" />
                  <YAxis />
                  <Tooltip formatter={(v: number) => formatMoney(v)} />
                  <Legend />
                  {categoryMonthChart.keys.map((k, i) => (
                    <Bar
                      key={k}
                      dataKey={k}
                      stackId="a"
                      fill={["#c45c26", "#1a1f2e", "#5c6478", "#2d6a4f", "#8b5a2b", "#4a5568"][i % 6]}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>
      )}
    </>
  );
}
