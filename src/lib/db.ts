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

/** A Category's Budget (null: none) beside what was spent, for one month. */
export interface BudgetLine {
  category: string;
  budget_cents: number | null;
  spent_cents: number;
}

export interface Statement {
  id: number;
  account_id: number;
  period_start: string;
  period_end: string;
  file_name: string | null;
  imported_at: string;
  transactions: number;
}

export interface Person {
  id: number;
  name: string;
  note: string | null;
  /** Positive: they owe you. Negative: you owe them. */
  balance_cents: number;
}

export interface Group {
  id: number;
  name: string;
  members: { id: number; name: string }[];
}

export interface SharedExpense {
  id: number;
  date: string;
  description: string;
  category: string;
  total_cents: number;
  your_share_cents: number;
  /** null: you paid. */
  paid_by: number | null;
  paid_by_name: string | null;
  group_id: number | null;
  group_name: string | null;
  standalone: boolean;
  from_splitwise: boolean;
  shares: { person_id: number; name: string; cents: number }[];
  transaction: { id: number; date: string; description: string; amount_cents: number } | null;
  /** Whether your Share counts as Spending yet. */
  counted: boolean;
}

export interface NewSharedExpense {
  date: string;
  description: string;
  category: string;
  total_cents: number;
  your_share_cents: number;
  paid_by: number | null;
  shares: { person_id: number; cents: number }[];
  group_id?: number | null;
  transaction_id?: number | null;
  standalone?: boolean;
}

export interface Settlement {
  id: number;
  date: string;
  person_id: number;
  name: string;
  cents: number;
  direction: "to_them" | "from_them";
  note: string | null;
}

export interface LinkSuggestion {
  expense_id: number;
  transaction_id: number;
  score: number;
  reason: string;
  expense: { id: number; date: string; description: string; total_cents: number };
  transaction: { id: number; date: string; description: string; amount_cents: number };
}

export interface SplitwisePreview {
  members: string[];
  rows: number;
  payments: number;
  first_date: string | null;
  last_date: string | null;
  rejected: Rejected;
}

export interface SplitwiseResult {
  imported: number;
  settlements: number;
  already_imported: number;
  not_involving_you: number;
  skipped: Rejected;
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

  getStatements: () => request<Statement[]>("/api/statements"),

  /** Removes the Statement with its Transactions and any edits made to them. */
  deleteStatement: (id: number) => request<{ ok: true }>(`/api/statements/${id}`, { method: "DELETE" }),

  getSpending: (month: string) => request<Spending>(`/api/spending/${month}`),

  getPeople: () => request<Person[]>("/api/people"),
  addPerson: (name: string, note?: string) =>
    request<{ id: number }>("/api/people", { method: "POST", body: JSON.stringify({ name, note: note || null }) }),
  deletePerson: (id: number) => request<{ ok: true }>(`/api/people/${id}`, { method: "DELETE" }),
  /** Records the Settlement that brings this Person's Balance to zero. */
  settleUp: (id: number, date: string) =>
    request<{ settlement_id: number | null }>(`/api/people/${id}/settle`, { method: "POST", body: JSON.stringify({ date }) }),

  getGroups: () => request<Group[]>("/api/groups"),
  addGroup: (name: string, memberIds: number[] = []) =>
    request<{ id: number }>("/api/groups", { method: "POST", body: JSON.stringify({ name, member_ids: memberIds }) }),
  addMember: (groupId: number, personId: number) =>
    request<{ ok: true }>(`/api/groups/${groupId}/members`, { method: "POST", body: JSON.stringify({ person_id: personId }) }),
  removeMember: (groupId: number, personId: number) =>
    request<{ ok: true }>(`/api/groups/${groupId}/members/${personId}`, { method: "DELETE" }),
  deleteGroup: (id: number) => request<{ ok: true }>(`/api/groups/${id}`, { method: "DELETE" }),

  getShared: (month?: string) => request<SharedExpense[]>(`/api/shared${month ? `?month=${month}` : ""}`),
  addShared: (expense: NewSharedExpense) =>
    request<{ id: number }>("/api/shared", { method: "POST", body: JSON.stringify(expense) }),
  deleteShared: (id: number) => request<{ ok: true }>(`/api/shared/${id}`, { method: "DELETE" }),
  /** Links the expense to the Purchase that paid for it; null unlinks. */
  linkShared: (id: number, transactionId: number | null) =>
    request<{ ok: true }>(`/api/shared/${id}/link`, { method: "POST", body: JSON.stringify({ transaction_id: transactionId }) }),
  /** Marks an expense you paid as paid outside your tracked accounts, so your Share counts. */
  setStandalone: (id: number, standalone: boolean) =>
    request<{ ok: true }>(`/api/shared/${id}/standalone`, { method: "POST", body: JSON.stringify({ standalone }) }),

  getSettlements: () => request<Settlement[]>("/api/settlements"),
  deleteSettlement: (id: number) => request<{ ok: true }>(`/api/settlements/${id}`, { method: "DELETE" }),

  getReconcile: () => request<{ suggestions: LinkSuggestion[]; unlinked: SharedExpense[] }>("/api/reconcile"),

  previewSplitwise: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<SplitwisePreview>("/api/splitwise/preview", { method: "POST", body: form });
  },
  importSplitwise: (file: File, yourName: string, groupName: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("your_name", yourName);
    if (groupName.trim()) form.append("group_name", groupName.trim());
    return request<SplitwiseResult>("/api/splitwise/import", { method: "POST", body: form });
  },

  getBudgets: (month: string) =>
    request<{ categories: BudgetLine[] }>(`/api/budgets/${month}`).then((r) => r.categories),

  /** Sets a Category's Budget from `month` on; null removes it from then. */
  setBudget: (month: string, category: string, amountCents: number | null) =>
    request<{ ok: true }>(`/api/budgets/${month}`, {
      method: "PUT",
      body: JSON.stringify({ category, amount_cents: amountCents }),
    }),

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

  getBackupLocation: () => request<{ directory: string; min_password: number }>("/api/backups"),

  /** No password saves a plain copy; a password saves an encrypted Backup. */
  saveBackup: (password: string | null) =>
    request<{ path: string; encrypted: boolean; size: number }>("/api/backups", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),

  /** Replaces all data with the Backup. `previous` is where the data as it was is saved. */
  restoreBackup: (file: File, password: string | null) => {
    const form = new FormData();
    form.append("file", file);
    if (password) form.append("password", password);
    return request<{ previous: string }>("/api/restore", { method: "POST", body: form });
  },
};
