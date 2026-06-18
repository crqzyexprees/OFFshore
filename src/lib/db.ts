const API_BASE =
  import.meta.env.VITE_API_URL ?? "http://127.0.0.1:18765";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export interface Account {
  id?: number;
  name: string;
  bank: string;
  last_four?: string;
  color?: string;
}

export interface Transaction {
  id?: number;
  account_id: number;
  date: string;
  description: string;
  merchant?: string;
  amount: number;
  tx_type: "debit" | "credit";
  category?: string;
  category_confidence?: number;
  manually_overridden?: boolean;
  manual_category?: string;
}

export interface ImportResult {
  imported: number;
  duplicates: number;
  failed: number;
  bank: string;
}

export const db = {
  getAccounts: () => request<Account[]>("/api/accounts"),

  addAccount: async (account: Account) => {
    const res = await request<{ id: number }>("/api/accounts", {
      method: "POST",
      body: JSON.stringify(account),
    });
    return res.id;
  },

  deleteAccount: (id: number) =>
    request<void>(`/api/accounts/${id}`, { method: "DELETE" }),

  getTransactions: (accountId?: number, month?: string, category?: string) => {
    const params = new URLSearchParams();
    if (accountId != null) params.set("account_id", String(accountId));
    if (month) params.set("month", month);
    if (category) params.set("category", category);
    const qs = params.toString();
    return request<Transaction[]>(`/api/transactions${qs ? `?${qs}` : ""}`);
  },

  getSpendingByCategory: (month: string) =>
    request<[string, number][]>(`/api/spending/${month}`),

  overrideCategory: (txId: number, category: string) =>
    request<void>(`/api/transactions/${txId}/category`, {
      method: "POST",
      body: JSON.stringify({ category }),
    }),

  importPdf: async (accountId: number): Promise<ImportResult> => {
    if (!window.electronAPI?.openPdfDialog) {
      throw new Error("PDF import requires the Electron app");
    }
    const pdfPath = await window.electronAPI.openPdfDialog();
    if (!pdfPath) throw new Error("No file selected");
    return request<ImportResult>("/api/import", {
      method: "POST",
      body: JSON.stringify({ pdf_path: pdfPath, account_id: accountId }),
    });
  },
};
