import { useEffect, useMemo, useState } from "react";
import { Pencil, ReceiptText, Search, X } from "lucide-react";
import { db, Account, Kind, Transaction } from "../lib/db";
import { categoryColor, CategoryIcon } from "../lib/categories";
import { formatMoney, hasCategory, kindName, useReference } from "../lib/reference";
import { Card, EmptyState, PageHeader } from "../components/ui";

type Editing = { id: number; field: "kind" | "category" } | null;

type Filter = { search: string; month: string; accountId: string; kind: string; category: string };
const NO_FILTER: Filter = { search: "", month: "", accountId: "", kind: "", category: "" };

// The last two years, newest first; <input type="month"> is poorly supported in WebKitGTK.
const RECENT_MONTHS = Array.from({ length: 24 }, (_, i) => {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - i);
  return {
    id: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`,
    label: d.toLocaleDateString(undefined, { month: "short", year: "numeric" }),
  };
});

const filterField = "border border-field rounded-lg px-2.5 py-1.5 text-sm";

export function Transactions({ accounts, onImport }: { accounts: Account[]; onImport: () => void }) {
  const reference = useReference();
  const [transactions, setTransactions] = useState<Transaction[] | null>(null);
  const [editing, setEditing] = useState<Editing>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>(NO_FILTER);

  const load = () =>
    db
      .getTransactions({
        month: filter.month || undefined,
        accountId: filter.accountId ? Number(filter.accountId) : undefined,
        kind: filter.kind || undefined,
        category: filter.category || undefined,
      })
      .then(setTransactions, (e) => setError(String(e)));

  useEffect(() => {
    load();
  }, [filter.month, filter.accountId, filter.kind, filter.category]);

  // Text search is done here so typing doesn't hit the backend on every key.
  const shown = useMemo(() => {
    const q = filter.search.trim().toLowerCase();
    return (transactions ?? []).filter((tx) => !q || tx.description.toLowerCase().includes(q));
  }, [transactions, filter.search]);

  const filtered = JSON.stringify(filter) !== JSON.stringify(NO_FILTER);
  const set = (part: Partial<Filter>) => setFilter((f) => ({ ...f, ...part }));
  const accountById = (id: number) => accounts.find((a) => a.id === id);

  // Each edit becomes an Override; the other part of the Override is kept.
  const handleOverride = async (tx: Transaction, change: { kind?: Kind; category?: string }) => {
    setEditing(null);
    try {
      const { repredicted } = await db.setOverride(tx.id, {
        kind: change.kind ?? tx.override_kind,
        category: change.category ?? tx.override_category,
      });
      setNotice(
        repredicted > 0
          ? `Learned from that: ${repredicted} other transaction${repredicted === 1 ? "" : "s"} updated.`
          : null
      );
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const isEditing = (tx: Transaction, field: "kind" | "category") =>
    editing?.id === tx.id && editing.field === field;

  if (transactions !== null && transactions.length === 0 && !filtered) {
    return (
      <div className="p-6 max-w-6xl">
        <PageHeader title="Transactions" />
        <Card>
          <EmptyState
            icon={<ReceiptText size={36} />}
            title="No transactions yet"
            hint="Import a statement and its transactions will show up here, already sorted into categories."
            action={
              <button onClick={onImport} className="text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:underline">
                Import a statement →
              </button>
            }
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl">
      <PageHeader title="Transactions" subtitle="Click a kind or category to correct it — your edits are kept when a statement is re-imported." />

      <div className="flex flex-wrap items-center gap-2 mb-3">
        <div className="relative flex-1 min-w-48">
          <Search size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-faint pointer-events-none" />
          <input
            placeholder="Search descriptions"
            value={filter.search}
            onChange={(e) => set({ search: e.target.value })}
            className={`${filterField} w-full pl-8`}
          />
        </div>
        <select value={filter.month} onChange={(e) => set({ month: e.target.value })} className={filterField}>
          <option value="">All months</option>
          {RECENT_MONTHS.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>
        {accounts.length > 1 && (
          <select value={filter.accountId} onChange={(e) => set({ accountId: e.target.value })} className={filterField}>
            <option value="">All accounts</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        )}
        <select value={filter.kind} onChange={(e) => set({ kind: e.target.value })} className={filterField}>
          <option value="">All kinds</option>
          {reference?.kinds.map((k) => (
            <option key={k.id} value={k.id}>
              {k.name}
            </option>
          ))}
        </select>
        <select value={filter.category} onChange={(e) => set({ category: e.target.value })} className={filterField}>
          <option value="">All categories</option>
          {reference?.categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        {filtered && (
          <button
            onClick={() => setFilter(NO_FILTER)}
            className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink px-2 py-1.5"
          >
            <X size={14} /> Clear
          </button>
        )}
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-400 mb-3">{error}</p>}
      {notice && (
        <p className="text-sm text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-900 rounded-lg px-3 py-2 mb-3 flex items-center justify-between">
          {notice}
          <button onClick={() => setNotice(null)} aria-label="Dismiss" className="ml-3 opacity-70 hover:opacity-100">
            <X size={14} />
          </button>
        </p>
      )}

      <Card className="overflow-hidden">
        {shown.length === 0 ? (
          <EmptyState icon={<Search size={32} />} title="Nothing matches these filters" />
        ) : (
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10">
              <tr className="text-left text-xs uppercase tracking-wide text-muted border-b border-line bg-surface-muted">
                <th className="py-2.5 px-4 font-medium">Date</th>
                <th className="py-2.5 px-4 font-medium">Description</th>
                <th className="py-2.5 px-4 font-medium">Kind</th>
                <th className="py-2.5 px-4 font-medium">Category</th>
                <th className="py-2.5 px-4 font-medium text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((tx) => {
                const account = accountById(tx.account_id);
                return (
                  <tr key={tx.id} className="border-b border-line-soft last:border-0 hover:bg-surface-muted/60">
                    <td className="py-2.5 px-4 text-muted whitespace-nowrap tabular-nums">{tx.date}</td>
                    <td className="py-2.5 px-4 max-w-xs">
                      <div className="flex items-center gap-2 min-w-0">
                        {accounts.length > 1 && account && (
                          <span
                            className="w-2 h-2 rounded-full shrink-0"
                            style={{ backgroundColor: account.color ?? "#6366f1" }}
                            title={account.name}
                          />
                        )}
                        <span className="truncate text-ink">{tx.description}</span>
                        {tx.overridden && (
                          <span title="Edited by you" className="text-faint shrink-0">
                            <Pencil size={12} />
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 px-4">
                      {isEditing(tx, "kind") ? (
                        <select
                          autoFocus
                          defaultValue={tx.kind}
                          onChange={(e) => handleOverride(tx, { kind: e.target.value })}
                          onBlur={() => setEditing(null)}
                          className="border border-field rounded px-2 py-1 text-sm"
                        >
                          {reference?.kinds.map((k) => (
                            <option key={k.id} value={k.id}>
                              {k.name}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <button
                          onClick={() => setEditing({ id: tx.id, field: "kind" })}
                          className="px-2 py-0.5 rounded-md border border-line text-xs text-ink-soft hover:border-field hover:bg-surface-muted"
                        >
                          {kindName(reference, tx.kind)}
                        </button>
                      )}
                    </td>
                    <td className="py-2.5 px-4">
                      {!hasCategory(reference, tx.kind) ? (
                        <span className="text-xs text-faint">—</span>
                      ) : isEditing(tx, "category") ? (
                        <select
                          autoFocus
                          defaultValue={tx.category ?? "Other"}
                          onChange={(e) => handleOverride(tx, { category: e.target.value })}
                          onBlur={() => setEditing(null)}
                          className="border border-field rounded px-2 py-1 text-sm"
                        >
                          {reference?.categories.map((c) => (
                            <option key={c} value={c}>
                              {c}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <button
                          onClick={() => setEditing({ id: tx.id, field: "category" })}
                          className="inline-flex items-center gap-1.5 pl-0.5 pr-2.5 py-0.5 rounded-full text-xs text-ink hover:brightness-110"
                          style={{ backgroundColor: `${categoryColor(tx.category ?? "Other")}22` }}
                        >
                          <CategoryIcon name={tx.category ?? "Other"} size={20} />
                          {tx.category}
                        </button>
                      )}
                    </td>
                    <td
                      className={`py-2.5 px-4 text-right font-medium whitespace-nowrap tabular-nums ${
                        tx.direction === "in" ? "text-emerald-700 dark:text-emerald-400" : "text-ink"
                      }`}
                    >
                      {tx.direction === "in" ? "+" : ""}
                      {formatMoney(tx.amount_cents)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>

      {shown.length > 0 && (
        <p className="text-xs text-muted mt-2 text-right tabular-nums">
          {shown.length} transaction{shown.length === 1 ? "" : "s"}
        </p>
      )}
    </div>
  );
}
