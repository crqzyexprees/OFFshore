import { useEffect, useMemo, useState } from "react";
import { Pencil, ReceiptText, Search, X } from "lucide-react";
import { db, Account, Kind, Spending, Transaction } from "../lib/db";
import { categoryColor, CategoryIcon } from "../lib/categories";
import { formatMoney, hasCategory, kindName, useReference } from "../lib/reference";
import { monthLabel, thisMonth } from "../lib/month";
import { MonthPicker } from "../components/MonthPicker";
import { CategoryBreakdown } from "../components/CategoryBreakdown";
import { Card, CardTitle, EmptyState, PageHeader, Stat, field } from "../components/ui";

type Editing = { id: number; field: "kind" | "category" } | null;

type Filter = { search: string; accountId: string; kind: string; category: string };
const NO_FILTER: Filter = { search: "", accountId: "", kind: "", category: "" };

export function Transactions({ accounts, onImport }: { accounts: Account[]; onImport: () => void }) {
  const reference = useReference();
  const [transactions, setTransactions] = useState<Transaction[] | null>(null);
  const [editing, setEditing] = useState<Editing>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>(NO_FILTER);
  const [month, setMonth] = useState(thisMonth);
  const [spending, setSpending] = useState<Spending | null>(null);

  const load = () => {
    db.getSpending(month).then(setSpending, () => setSpending(null));
    return db
      .getTransactions({
        month,
        accountId: filter.accountId ? Number(filter.accountId) : undefined,
        kind: filter.kind || undefined,
        category: filter.category || undefined,
      })
      .then(setTransactions, (e) => setError(String(e)));
  };

  useEffect(() => {
    load();
  }, [month, filter.accountId, filter.kind, filter.category]);

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

  const total = (spending?.categories ?? []).reduce((sum, c) => sum + c.cents, 0);
  const top = [...(spending?.categories ?? [])].sort((x, y) => y.cents - x.cents)[0];

  return (
    <div>
      <PageHeader
        title="Personal transactions"
        subtitle="Click a kind or category to correct it. Your edits are kept when a statement is imported again."
        actions={<MonthPicker month={month} onChange={setMonth} latest={thisMonth()} />}
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Stat label="Total spent" value={formatMoney(total)} caption={`For ${monthLabel(month)}`} />
        <Stat
          label="Top category"
          value={top && top.cents > 0 ? formatMoney(top.cents) : "—"}
          caption={top && top.cents > 0 ? top.category : "No spending yet"}
        />
        <Stat
          label="Transactions"
          value={transactions?.length ?? "—"}
          caption={filtered ? "Matching the filters below" : "Every kind, this month"}
        />
      </div>

      {spending && spending.categories.length > 0 && (
        <Card className="p-6 mb-6">
          <CardTitle>Spending by category</CardTitle>
          <CategoryBreakdown categories={spending.categories} />
        </Card>
      )}

      {error && <p className="text-sm text-red-600 dark:text-red-400 mb-3">{error}</p>}
      {notice && (
        <p className="text-sm text-ink bg-surface border border-line rounded-lg px-4 py-2.5 mb-3 flex items-center justify-between">
          {notice}
          <button onClick={() => setNotice(null)} aria-label="Dismiss" className="ml-3 opacity-70 hover:opacity-100">
            <X size={14} />
          </button>
        </p>
      )}

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 border-b border-line p-4">
          <div className="relative flex-1 min-w-48">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-faint pointer-events-none" />
            <input
              placeholder="Search merchants"
              value={filter.search}
              onChange={(e) => set({ search: e.target.value })}
              className={`${field} w-full pl-9`}
            />
          </div>
          {accounts.length > 1 && (
            <select value={filter.accountId} onChange={(e) => set({ accountId: e.target.value })} className={field}>
              <option value="">All accounts</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          )}
          <select value={filter.kind} onChange={(e) => set({ kind: e.target.value })} className={field}>
            <option value="">All kinds</option>
            {reference?.kinds.map((k) => (
              <option key={k.id} value={k.id}>
                {k.name}
              </option>
            ))}
          </select>
          <select value={filter.category} onChange={(e) => set({ category: e.target.value })} className={field}>
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
        {shown.length === 0 ? (
          filtered ? (
            <EmptyState icon={<Search size={32} />} title="Nothing matches these filters" />
          ) : (
            <EmptyState
              icon={<ReceiptText size={36} />}
              title={`No transactions in ${monthLabel(month)}`}
              hint="Upload a statement and its transactions show up here, already sorted into categories."
              action={
                <button onClick={onImport} className="text-sm font-medium text-ink underline underline-offset-4 hover:no-underline">
                  Upload a statement
                </button>
              }
            />
          )
        ) : (
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10">
              <tr className="text-left text-sm text-muted border-b border-line bg-surface-muted">
                <th className="py-3 px-4 font-medium">Date</th>
                <th className="py-3 px-4 font-medium">Merchant</th>
                <th className="py-3 px-4 font-medium">Kind</th>
                <th className="py-3 px-4 font-medium">Category</th>
                <th className="py-3 px-4 font-medium text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((tx) => {
                const account = accountById(tx.account_id);
                return (
                  <tr key={tx.id} className="border-b border-line-soft last:border-0 hover:bg-surface-muted/50">
                    <td className="py-3 px-4 text-muted whitespace-nowrap tabular-nums">{tx.date}</td>
                    <td className="py-3 px-4 max-w-xs">
                      <div className="flex items-center gap-2 min-w-0">
                        {accounts.length > 1 && account && (
                          <span
                            className="w-2 h-2 rounded-full shrink-0"
                            style={{ backgroundColor: account.color ?? "#71717a" }}
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
                    <td className="py-3 px-4">
                      {isEditing(tx, "kind") ? (
                        <select
                          autoFocus
                          defaultValue={tx.kind}
                          onChange={(e) => handleOverride(tx, { kind: e.target.value })}
                          onBlur={() => setEditing(null)}
                          className="border border-line rounded-md px-2 py-1 text-sm"
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
                    <td className="py-3 px-4">
                      {!hasCategory(reference, tx.kind) ? (
                        <span className="text-xs text-faint">—</span>
                      ) : isEditing(tx, "category") ? (
                        <select
                          autoFocus
                          defaultValue={tx.category ?? "Other"}
                          onChange={(e) => handleOverride(tx, { category: e.target.value })}
                          onBlur={() => setEditing(null)}
                          className="border border-line rounded-md px-2 py-1 text-sm"
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
                      className={`py-3 px-4 text-right font-medium whitespace-nowrap tabular-nums ${
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
