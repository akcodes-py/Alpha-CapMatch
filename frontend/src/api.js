const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(org, path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { "X-Organization": org, ...(options.headers || {}) },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data?.error?.message || `Request failed (${res.status})`);
  }
  return data;
}

export const api = {
  listTransactions: (org) => request(org, "/api/transactions/"),
  listLineItems: (org) => request(org, "/api/line-items/"),
  approveMatch: (org, id) =>
    request(org, `/api/matches/${id}/approve/`, { method: "POST" }),
  rejectMatch: (org, id) =>
    request(org, `/api/matches/${id}/reject/`, { method: "POST" }),
  ignoreTransaction: (org, id) =>
    request(org, `/api/transactions/${id}/ignore/`, { method: "POST" }),
  unignoreTransaction: (org, id) =>
    request(org, `/api/transactions/${id}/unignore/`, { method: "POST" }),
  transactionHistory: (org, id) => request(org, `/api/transactions/${id}/history/`),
  importCsv: async (org, file) => {
    const form = new FormData();
    form.append("file", file);
    return request(org, "/api/imports/", { method: "POST", body: form });
  },
  previewCsv: async (org, file) => {
    const form = new FormData();
    form.append("file", file);
    return request(org, "/api/imports/preview/", { method: "POST", body: form });
  },
};

export const money = (value) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  }).format(Number(value));

export const STATUS_LABELS = {
  suggested: "Suggested",
  needs_review: "Needs review",
  reconciled: "Reconciled",
  ignored: "Ignored",
  open: "Open",
  partially_funded: "Partially funded",
  funded: "Funded",
  proposed: "Proposed",
  approved: "Approved",
  rejected: "Rejected",
};

export const statusLabel = (value) => STATUS_LABELS[value] || value;

export const RULE_LABELS = {
  reference: "reference",
  name_and_amount: "name + amount",
};

export const ruleLabel = (value) => RULE_LABELS[value] || value;

export async function downloadNeedsReviewCsv(org) {
  const res = await fetch(`${BASE}/api/transactions/export/?status=needs_review`, {
    headers: { "X-Organization": org },
  });
  if (!res.ok) throw new Error(`Export failed (${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "needs_review.csv";
  a.click();
  URL.revokeObjectURL(url);
}
