const state = {
  tab: "upload",
  categories: [],
  transactions: [],
  insights: null,
  filters: { bank: "", category: "", date_from: "", date_to: "", account_last4: "" },
  uploads: [],
  accounts: [],
  categorizeStatus: { llm_available: false, unknown_count: 0 },
  txnSort: { key: "posted_date", dir: "desc" },
};

const tabsEl = document.getElementById("tabs");
const panelEl = document.getElementById("panel");
const alertEl = document.getElementById("alert");

function money(n) {
  return Number(n).toLocaleString(undefined, { style: "currency", currency: "USD" });
}

function computeFilteredTotals(txns) {
  let spend = 0;
  let credits = 0;
  let unknowns = 0;
  for (const t of txns) {
    if (t.category === "Unknown") unknowns += 1;
    if (t.amount < 0 && t.category !== "Transfer" && t.category !== "Income") {
      spend += -t.amount;
    } else if (t.amount > 0 && t.category === "Income") {
      credits += t.amount;
    }
  }
  return { spend, credits, count: txns.length, unknowns };
}

function sortIndicator(key) {
  if (state.txnSort.key !== key) return "";
  return state.txnSort.dir === "asc" ? " ↑" : " ↓";
}

function sortedTransactions(txns) {
  const { key, dir } = state.txnSort;
  const mul = dir === "asc" ? 1 : -1;
  return [...txns].sort((a, b) => {
    if (key === "amount") {
      if (a.amount === b.amount) return 0;
      return mul * (a.amount - b.amount);
    }
    if (key === "posted_date") {
      return mul * a.posted_date.localeCompare(b.posted_date);
    }
    return 0;
  });
}

function periodLabel(filters) {
  const parts = [];
  if (filters.date_from) parts.push(`from ${filters.date_from}`);
  if (filters.date_to) parts.push(`through ${filters.date_to}`);
  if (filters.category) parts.push(filters.category);
  if (filters.bank) parts.push(filters.bank);
  if (filters.account_last4) {
    const acct = state.accounts.find((a) => a.account_last4 === filters.account_last4);
    parts.push(acct ? acct.label : `••${filters.account_last4}`);
  }
  return parts.length ? parts.join(" · ") : "all imported transactions";
}

function showError(msg) {
  if (!msg) {
    alertEl.hidden = true;
    return;
  }
  alertEl.hidden = false;
  alertEl.textContent = msg;
}

function qs(params) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v) q.set(k, v);
  });
  const s = q.toString();
  return s ? `?${s}` : "";
}

async function api(path, init) {
  const res = await fetch(path, { cache: "no-store", ...init });
  const text = await res.text();
  if (!res.ok) {
    try {
      const err = JSON.parse(text);
      if (err.detail) throw new Error(typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail));
    } catch (parseErr) {
      if (parseErr instanceof Error && parseErr.message !== text) throw parseErr;
    }
    throw new Error(text || res.statusText);
  }
  return text ? JSON.parse(text) : {};
}

async function refresh() {
  const f = state.filters;
  const [cats, txns, insights, uploads, accounts, catStatus] = await Promise.all([
    api("/api/categories"),
    api(`/api/transactions${qs(f)}`),
    api("/api/insights"),
    api("/api/uploads"),
    api("/api/accounts"),
    api("/api/categorize/status"),
  ]);
  state.categories = cats.categories;
  state.transactions = txns.transactions;
  state.insights = insights;
  state.uploads = uploads.uploads;
  state.accounts = accounts.accounts;
  state.categorizeStatus = catStatus;
}

function renderTabs() {
  tabsEl.innerHTML = "";
  ["upload", "transactions", "insights"].forEach((t) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = `tab ${state.tab === t ? "active" : ""}`;
    b.textContent = t[0].toUpperCase() + t.slice(1);
    b.onclick = () => {
      state.tab = t;
      render();
    };
    tabsEl.appendChild(b);
  });
}

let monthChart;
let stackChart;

function renderInsights() {
  const ins = state.insights;
  if (!ins) return "<p class='muted'>No data yet.</p>";
  const mom =
    ins.month_over_month_delta_pct === null
      ? "—"
      : `${ins.month_over_month_delta_pct > 0 ? "+" : ""}${ins.month_over_month_delta_pct}%`;

  setTimeout(() => {
    const mctx = document.getElementById("monthChart");
    if (mctx && window.Chart) {
      if (monthChart) monthChart.destroy();
      monthChart = new Chart(mctx, {
        type: "bar",
        data: {
          labels: ins.by_month.map((m) => m.month),
          datasets: [
            { label: "Spend", data: ins.by_month.map((m) => m.spend || 0), backgroundColor: "#c45c26" },
            { label: "Income", data: ins.by_month.map((m) => m.income || 0), backgroundColor: "#2d6a4f" },
          ],
        },
      });
    }
    const sctx = document.getElementById("stackChart");
    const months = [...new Set(ins.by_month_category.map((r) => r.month))].sort();
    const cats = [...new Set(ins.by_month_category.map((r) => r.category))].slice(0, 6);
    if (sctx && cats.length && window.Chart) {
      if (stackChart) stackChart.destroy();
      const colors = ["#c45c26", "#1a1f2e", "#5c6478", "#2d6a4f", "#8b5a2b", "#4a5568"];
      stackChart = new Chart(sctx, {
        type: "bar",
        data: {
          labels: months,
          datasets: cats.map((c, i) => ({
            label: c,
            data: months.map((month) => {
              const row = ins.by_month_category.find((r) => r.month === month && r.category === c);
              return row ? row.spend : 0;
            }),
            backgroundColor: colors[i % colors.length],
          })),
        },
        options: { scales: { x: { stacked: true }, y: { stacked: true } } },
      });
    }
  }, 0);

  return `
    <div class="kpi-grid">
      <div class="kpi"><label>Total spend</label><div><strong>${money(ins.total_spend)}</strong></div></div>
      <div class="kpi"><label>Top category</label><div><strong>${ins.top_category || "—"} (${money(ins.top_category_spend)})</strong></div></div>
      <div class="kpi"><label>Latest month</label><div><strong>${ins.latest_month || "—"} · ${money(ins.latest_month_spend)}</strong></div></div>
      <div class="kpi"><label>Month vs prior</label><div><strong>${mom}</strong></div></div>
    </div>
    ${ins.by_month.length ? "" : "<p class='muted'>Upload a statement to see monthly charts.</p>"}
    <canvas id="monthChart" height="120"></canvas>
    ${ins.by_month_category.length ? "" : ""}
    <canvas id="stackChart" height="120" style="margin-top:1.5rem"></canvas>
  `;
}

function renderTransactions() {
  const banks = [...new Set(state.transactions.map((t) => t.bank))].sort();
  const totals = computeFilteredTotals(state.transactions);
  const cs = state.categorizeStatus;
  const llmLabel =
    cs.unknown_count > 0
      ? `Categorize unknowns with AI (${cs.unknown_count} total)`
      : "Categorize unknowns with AI";
  const llmHint = cs.llm_available
    ? "Uses your Anthropic key from .env (Haiku). AI-assigned categories are kept across recategorize and re-import."
    : "Add ANTHROPIC_API_KEY to .env and restart ./run.sh serve.";
  const displayTxns = sortedTransactions(state.transactions);
  const rows = displayTxns
    .map(
      (t) => `
    <tr>
      <td>${t.posted_date}</td>
      <td>${escapeHtml(t.description)}</td>
      <td class="amount ${t.amount < 0 ? "neg" : "pos"}">${money(t.amount)}</td>
      <td>
        <select data-id="${t.id}" class="cat-select">
          ${state.categories.map((c) => `<option value="${c}" ${c === t.category ? "selected" : ""}>${c}</option>`).join("")}
        </select>
      </td>
      <td>${escapeHtml(t.account_label || t.bank)}</td>
    </tr>`,
    )
    .join("");

  return `
    <div class="filters">
      <select id="f-card"><option value="">All cards</option>${state.accounts.map((a) => `<option value="${a.account_last4 || ""}" ${state.filters.account_last4 === (a.account_last4 || "") ? "selected" : ""}>${escapeHtml(a.label)}</option>`).join("")}</select>
      <select id="f-bank"><option value="">All banks</option>${banks.map((b) => `<option value="${b}" ${state.filters.bank === b ? "selected" : ""}>${b}</option>`).join("")}</select>
      <select id="f-category"><option value="">All categories</option>${state.categories.map((c) => `<option value="${c}" ${state.filters.category === c ? "selected" : ""}>${c}</option>`).join("")}</select>
      <input type="date" id="f-from" value="${state.filters.date_from}" />
      <input type="date" id="f-to" value="${state.filters.date_to}" />
    </div>
    <div class="actions">
      <button type="button" class="btn secondary" id="copy-excel">Copy for Excel</button>
      <a class="btn secondary" href="/api/export.xlsx${qs(state.filters)}">Download .xlsx</a>
      <button type="button" class="btn secondary" id="llm-txn-btn" ${cs.llm_available ? "" : "disabled"}>${llmLabel}</button>
      <button type="button" class="btn secondary" id="filter-unknown">Unknown only</button>
    </div>
    <p class="muted txn-hint">${escapeHtml(llmHint)}</p>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th><button type="button" class="th-sort" data-sort="posted_date">Date${sortIndicator("posted_date")}</button></th>
          <th>Description</th>
          <th><button type="button" class="th-sort" data-sort="amount">Amount${sortIndicator("amount")}</button></th>
          <th>Category</th>
          <th>Card</th>
        </tr></thead>
        <tbody>${rows || `<tr><td colspan="5" class="muted">No transactions yet.</td></tr>`}</tbody>
      </table>
    </div>
    <div class="txn-summary">
      <div><span class="muted">Showing</span> <strong>${totals.count}</strong> <span class="muted">rows · ${escapeHtml(periodLabel(state.filters))}</span></div>
      <div class="txn-summary-grid">
        <div><span class="muted">Spend</span> <strong>${money(totals.spend)}</strong> <span class="muted">(excl. transfers & income)</span></div>
        <div><span class="muted">Income & reimbursements</span> <strong>${money(totals.credits)}</strong></div>
        <div><span class="muted">Unknown in view</span> <strong>${totals.unknowns}</strong></div>
      </div>
    </div>
    <div id="txn-status" class="muted"></div>`;
}

function renderUpload() {
  const list = state.uploads
    .map(
      (u) => `
    <div class="upload-row" style="display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:0.65rem 0;border-bottom:1px solid var(--border)">
      <div>
        <strong>${escapeHtml(u.filename)}</strong>
        <div class="muted">#${u.id} · ${escapeHtml(u.account_label || u.bank)} · ${u.transaction_count} transactions · ${escapeHtml(u.created_at.slice(0, 10))}</div>
      </div>
      <button type="button" class="btn secondary" data-delete-upload="${u.id}">Remove</button>
    </div>`,
    )
    .join("");
  const removeAll =
    state.uploads.length > 0
      ? `<div class="actions" style="margin-top:0.75rem"><button type="button" class="btn secondary" id="delete-all-uploads">Remove all (${state.uploads.length})</button></div>`
      : "";
  const cs = state.categorizeStatus;
  const llmLabel =
    cs.unknown_count > 0
      ? `Categorize unknowns with AI (${cs.unknown_count})`
      : "Categorize unknowns with AI";
  const llmStatus = cs.llm_available
    ? `<span class="llm-status llm-ready">API key loaded · ${cs.unknown_count} unknown(s)</span>`
    : `<span class="llm-status llm-missing">Add ANTHROPIC_API_KEY to .env and restart ./run.sh serve</span>`;
  return `
    <div class="dropzone" id="dropzone">
      <p><strong>Drop PDF statements or Venmo CSVs</strong> or choose files</p>
      <p class="muted">Chase, Bank of America, Wells Fargo, Capital One + generic fallback</p>
      <label class="btn" style="margin-top:1rem;display:inline-block">Choose statements<input type="file" id="file-input" accept=".pdf,application/pdf,.csv,text/csv" multiple hidden /></label>
    </div>
    <div class="actions llm-actions" style="margin-top:1rem;align-items:center">
      <button type="button" class="btn secondary" id="llm-btn" ${cs.llm_available ? "" : "disabled"}>${llmLabel}</button>
      ${llmStatus}
    </div>
    <div id="upload-log" class="upload-log muted" role="status" aria-live="polite"></div>
    <h3 style="margin-top:1.5rem">Imported statements</h3>
    <p class="muted">PDF bank statements and Venmo CSV exports. Re-uploading the same file creates duplicate rows unless Venmo ID dedupes it.</p>
    ${removeAll}
    <div id="upload-list">${list || "<p class='muted'>No statements imported yet.</p>"}</div>`;
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function render() {
  renderTabs();
  panelEl.className = "panel";
  if (state.tab === "upload") panelEl.innerHTML = renderUpload();
  if (state.tab === "transactions") panelEl.innerHTML = renderTransactions();
  if (state.tab === "insights") panelEl.innerHTML = renderInsights();
  bindPanelEvents();
}

function bindPanelEvents() {
  const dz = document.getElementById("dropzone");
  const fi = document.getElementById("file-input");
  if (dz && fi) {
    dz.ondragover = (e) => {
      e.preventDefault();
      dz.classList.add("drag");
    };
    dz.ondragleave = () => dz.classList.remove("drag");
    dz.ondrop = (e) => {
      e.preventDefault();
      dz.classList.remove("drag");
      uploadFiles(e.dataTransfer.files);
    };
    fi.onchange = () => void uploadFiles(fi.files);
  }
  async function runLlmCategorize(statusEl, clickedBtn) {
    const llmButtons = ["llm-btn", "llm-txn-btn"]
      .map((id) => document.getElementById(id))
      .filter(Boolean);
    const labels = new Map(llmButtons.map((b) => [b, b.textContent]));
    const setBusy = (busy) => {
      llmButtons.forEach((b) => {
        b.classList.toggle("is-busy", busy);
        b.disabled = busy || !state.categorizeStatus.llm_available;
        b.textContent = busy ? "Categorizing…" : labels.get(b) || b.textContent;
      });
      if (clickedBtn) clickedBtn.setAttribute("aria-pressed", busy ? "true" : "false");
    };
    try {
      showError(null);
      setBusy(true);
      const logEl = document.getElementById("upload-log");
      if (logEl) {
        logEl.className = "upload-log muted is-running";
        logEl.textContent = "Running AI categorization…";
      }
      if (statusEl && statusEl !== logEl) statusEl.textContent = "Running AI categorization…";
      const r = await api("/api/categorize/unknowns", { method: "POST" });
      const msg = `Done — categorized ${r.updated} transaction(s). ${r.remaining_unknowns} unknown(s) left.`;
      if (logEl) {
        logEl.className = "upload-log is-success";
        logEl.textContent = msg;
      }
      if (statusEl && statusEl !== logEl) {
        statusEl.textContent = msg;
      }
      await reload();
    } catch (e) {
      showError(e.message);
      const logEl = document.getElementById("upload-log");
      if (logEl) {
        logEl.className = "upload-log is-error";
        logEl.textContent = "Categorization failed. See message above.";
      }
      if (statusEl && statusEl !== logEl) statusEl.textContent = "";
      setBusy(false);
    }
  }

  const llm = document.getElementById("llm-btn");
  if (llm) {
    llm.onclick = () => runLlmCategorize(document.getElementById("upload-log"), llm);
  }
  const llmTxn = document.getElementById("llm-txn-btn");
  if (llmTxn) {
    llmTxn.onclick = () => runLlmCategorize(document.getElementById("txn-status"), llmTxn);
  }
  const filterUnknown = document.getElementById("filter-unknown");
  if (filterUnknown) {
    filterUnknown.onclick = async () => {
      state.filters.category = state.filters.category === "Unknown" ? "" : "Unknown";
      await reload(false);
    };
  }

  document.querySelectorAll(".th-sort").forEach((btn) => {
    btn.onclick = () => {
      const key = btn.getAttribute("data-sort");
      if (!key) return;
      if (state.txnSort.key === key) {
        state.txnSort.dir = state.txnSort.dir === "asc" ? "desc" : "asc";
      } else {
        state.txnSort.key = key;
        state.txnSort.dir = "desc";
      }
      panelEl.innerHTML = renderTransactions();
      bindPanelEvents();
    };
  });

  ["f-card", "f-bank", "f-category", "f-from", "f-to"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.onchange = async () => {
      state.filters.account_last4 = document.getElementById("f-card")?.value || "";
      state.filters.bank = document.getElementById("f-bank").value;
      state.filters.category = document.getElementById("f-category").value;
      state.filters.date_from = document.getElementById("f-from").value;
      state.filters.date_to = document.getElementById("f-to").value;
      await reload(false);
    };
  });

  document.querySelectorAll(".cat-select").forEach((sel) => {
    sel.onchange = async () => {
      const id = sel.getAttribute("data-id");
      await api(`/api/transactions/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: sel.value, save_pattern: true }),
      });
      await reload(false);
    };
  });

  async function removeUpload(id) {
    let result;
    try {
      result = await api(`/api/uploads/${id}`, { method: "DELETE" });
    } catch {
      result = await api(`/api/uploads/${id}/delete`, { method: "POST" });
    }
    state.uploads = state.uploads.filter((u) => String(u.id) !== String(id));
    if (result.remaining_same_filename > 0) {
      showError(
        `Removed import #${id}. ${result.remaining_same_filename} duplicate row(s) with the same filename remain — remove those too or use Remove all.`,
      );
    } else {
      showError(null);
    }
    await reload();
  }

  document.querySelectorAll("[data-delete-upload]").forEach((btn) => {
    btn.onclick = async () => {
      const id = btn.getAttribute("data-delete-upload");
      const row = state.uploads.find((u) => String(u.id) === id);
      const name = row ? row.filename : "this statement";
      if (!window.confirm(`Remove import #${id} (${name})? This deletes its transactions and stored PDF copy.`)) {
        return;
      }
      try {
        await removeUpload(id);
      } catch (e) {
        showError(e instanceof Error ? e.message : "Delete failed");
      }
    };
  });

  const deleteAllBtn = document.getElementById("delete-all-uploads");
  if (deleteAllBtn) {
    deleteAllBtn.onclick = async () => {
      if (
        !window.confirm(
          `Remove all ${state.uploads.length} imported statements? This clears every transaction and PDF.`,
        )
      ) {
        return;
      }
      try {
        await api("/api/uploads", { method: "DELETE" });
        state.uploads = [];
        showError(null);
        await reload();
      } catch (e) {
        showError(e instanceof Error ? e.message : "Delete all failed");
      }
    };
  }

  const copyBtn = document.getElementById("copy-excel");
  if (copyBtn) {
    copyBtn.onclick = async () => {
      const res = await fetch(`/api/export.tsv${qs(state.filters)}`);
      const tsv = await res.text();
      await navigator.clipboard.writeText(tsv);
      copyBtn.textContent = "Copied!";
      setTimeout(() => (copyBtn.textContent = "Copy for Excel"), 1500);
    };
  }
}

async function uploadFiles(files) {
  if (!files?.length) return;
  const log = document.getElementById("upload-log");
  showError(null);
  if (log) log.innerHTML = "<p class='muted'>Uploading…</p>";
  try {
    let anyParsed = false;
    for (const file of files) {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/uploads", { method: "POST", body: form });
      const body = await res.text();
      if (!res.ok) {
        let msg = body;
        try {
          const j = JSON.parse(body);
          msg = j.detail || body;
        } catch {
          /* plain text */
        }
        showError(msg);
        if (log) log.innerHTML = "";
        return;
      }
      const r = JSON.parse(body);
      const warn =
        r.parsed_count === 0
          ? " No transactions parsed — open Transactions or re-upload after updating the app."
          : "";
      if (log) {
        log.innerHTML += `<div><strong>${file.name}</strong> — ${r.bank}: ${r.inserted} imported (${r.parsed_count} parsed).${warn} ${(r.warnings || []).join(" ")}</div>`;
      }
      if (r.parsed_count > 0) anyParsed = true;
      if (r.parsed_count === 0) {
        showError(`Upload saved but 0 transactions were found in ${file.name}.`);
      }
    }
    state.tab = anyParsed ? "transactions" : "upload";
    await reload();
  } catch (e) {
    showError(e instanceof Error ? e.message : "Upload failed");
    if (log) log.innerHTML = "";
  }
}

async function reload(rerenderTabs = true) {
  try {
    await refresh();
    showError(null);
    if (rerenderTabs) render();
    else {
      if (state.tab === "transactions") panelEl.innerHTML = renderTransactions();
      if (state.tab === "insights") panelEl.innerHTML = renderInsights();
      bindPanelEvents();
    }
  } catch (e) {
    showError(e.message);
  }
}

reload();
