export type Transaction = {
  id: number;
  upload_id: number;
  bank: string;
  account_last4: string | null;
  posted_date: string;
  description: string;
  amount: number;
  category: string;
  category_source: string;
};

export type UploadResult = {
  upload_id: number;
  bank: string;
  parsed_count: number;
  inserted: number;
  skipped_duplicates: number;
  warnings: string[];
};

export type Insights = {
  total_spend: number;
  top_category: string | null;
  top_category_spend: number;
  latest_month: string | null;
  latest_month_spend: number;
  month_over_month_delta_pct: number | null;
  by_month: { month: string; spend: number; income: number }[];
  by_month_category: { month: string; category: string; spend: number }[];
  by_category: { category: string; spend: number; count: number }[];
};

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || res.statusText);
  }
  return res.json() as Promise<T>;
}

export function fetchCategories() {
  return json<{ categories: string[] }>("/api/categories");
}

export function fetchTransactions(params: Record<string, string>) {
  const q = new URLSearchParams(params);
  return json<{ transactions: Transaction[] }>(`/api/transactions?${q}`);
}

export function fetchInsights() {
  return json<Insights>("/api/insights");
}

export async function uploadPdf(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/uploads", { method: "POST", body: form });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}

export function patchCategory(id: number, category: string) {
  return json<{ transaction: Transaction }>(`/api/transactions/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category, save_pattern: true }),
  });
}

export function categorizeUnknowns() {
  return json<{ updated: number }>("/api/categorize/unknowns", { method: "POST" });
}

export function exportTsvUrl(params: Record<string, string>) {
  const q = new URLSearchParams(params);
  return `/api/export.tsv?${q}`;
}

export function exportXlsxUrl(params: Record<string, string>) {
  const q = new URLSearchParams(params);
  return `/api/export.xlsx?${q}`;
}
