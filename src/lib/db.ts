import { connectBackend } from "./backend";

/** A failed request. `problem` is set when an import can't go ahead as asked. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly problem?: ImportProblem
  ) {
    super(message);
  }
}

type Rejected = { line: string; reason: string }[];

/**
 * Why a Statement couldn't be imported. Mirrors the ImportProblem classes in
 * backend/statement_import/__init__.py (tests/test_api.py checks they match).
 */
export type ImportProblem = { message: string } & (
  | { problem: "import_failed" }
  | { problem: "needs_account"; bank: string | null; last_four: string | null }
  | { problem: "needs_period"; account_id: number }
  | { problem: "account_mismatch"; bank: string | null; last_four: string | null }
  | { problem: "no_transactions"; rejected: Rejected }
);

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const { url, token } = await connectBackend();
  // FormData bodies must let the browser set their own multipart Content-Type.
  const jsonHeaders: Record<string, string> =
    init?.body instanceof FormData ? {} : { "Content-Type": "application/json" };
  if (token) jsonHeaders.Authorization = `Bearer ${token}`;
  const res = await fetch(`${url}${path}`, {
    ...init,
    headers: { ...jsonHeaders, ...init?.headers },
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      throw new ApiError(detail.message ?? `Request failed: ${res.status}`, res.status, detail as ImportProblem);
    }
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((e: { msg: string }) => e.msg).join("; ")
          : `Request failed: ${res.status}`;
    throw new ApiError(message, res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

/** Kinds come from the backend's vocabulary (see Reference), not from here. */
export type AccountKind = string;
export type Kind = string;

export interface Account {
  id?: number;
  name: string;
  kind: AccountKind;
  bank: string;
  last_four?: string;
  color?: string;
}

export interface Transaction {
  id: number;
  account_id: number;
  statement_id: number;
  date: string;
  description: string;
  amount_cents: number;
  direction: "in" | "out";
  kind: Kind;
  /** Only categorized kinds (Reference.categorized_kinds) have a Category. */
  category: string | null;
  category_confidence: number | null;
  overridden: boolean;
  override_kind: Kind | null;
  override_category: string | null;
}

type Named = { id: string; name: string };

/** The domain's vocabularies, as the backend defines them (backend/vocabulary.py). */
export interface Reference {
  banks: Named[];
  kinds: Named[];
  categorized_kinds: Kind[];
  account_kinds: Named[];
  categories: string[];
}

export interface Spending {
  categories: { category: string; cents: number }[];
  withdrawn_cents: number;
}

export interface ImportResult {
  statement_id: number;
  account_id: number;
  bank: string | null;
  period_start: string;
  period_end: string;
  imported: number;
  replaced: boolean;
  rejected: Rejected;
  unmatched_overrides: {
    date: string;
    description: string;
    amount_cents: number;
    direction: "in" | "out";
    override_kind: Kind | null;
    override_category: string | null;
  }[];
}

export interface ImportOptions {
  accountId?: number;
  period?: { start: string; end: string };
}

export const db = {
  getReference: () => request<Reference>("/api/reference"),

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

  getTransactions: (filter: { accountId?: number; month?: string; category?: string; kind?: Kind } = {}) => {
    const params = new URLSearchParams();
    if (filter.accountId != null) params.set("account_id", String(filter.accountId));
    if (filter.month) params.set("month", filter.month);
    if (filter.category) params.set("category", filter.category);
    if (filter.kind) params.set("kind", filter.kind);
    const qs = params.toString();
    return request<Transaction[]>(`/api/transactions${qs ? `?${qs}` : ""}`);
  },

  getSpending: (month: string) => request<Spending>(`/api/spending/${month}`),

  /**
   * Sets both parts of a Transaction's Override; null clears that part.
   * `repredicted` is how many other Transactions' Categories changed as a result.
   */
  setOverride: (txId: number, override: { kind: Kind | null; category: string | null }) =>
    request<{ repredicted: number }>(`/api/transactions/${txId}/override`, {
      method: "POST",
      body: JSON.stringify(override),
    }),

  importStatement: (file: File, options: ImportOptions = {}) => {
    const form = new FormData();
    form.append("file", file);
    if (options.accountId != null) form.append("account_id", String(options.accountId));
    if (options.period) {
      form.append("period_start", options.period.start);
      form.append("period_end", options.period.end);
    }
    return request<ImportResult>("/api/import", { method: "POST", body: form });
  },
};
