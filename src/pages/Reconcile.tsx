import { useEffect, useState } from "react";
import { db, LinkSuggestion, SharedExpense, Transaction } from "../lib/db";
import { formatMoney } from "../lib/reference";
import { Card, CardTitle, PageHeader, Stat, buttonGhost, buttonPrimary, field } from "../components/ui";

const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e));
const DAY = 24 * 60 * 60 * 1000;
const daysApart = (a: string, b: string) => Math.abs(new Date(a).getTime() - new Date(b).getTime()) / DAY;

export function Reconcile({ onImportSplitwise }: { onImportSplitwise: () => void }) {
  const [suggestions, setSuggestions] = useState<LinkSuggestion[]>([]);
  const [waiting, setWaiting] = useState<SharedExpense[] | null>(null);
  const [linked, setLinked] = useState<SharedExpense[]>([]);
  const [purchases, setPurchases] = useState<Transaction[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const [reconcile, all, txs] = await Promise.all([db.getReconcile(), db.getShared(), db.getTransactions({ kind: "purchase" })]);
      setSuggestions(reconcile.suggestions);
      setSelected(new Set(reconcile.suggestions.map((s) => s.expense_id)));
      setWaiting(reconcile.unlinked);
      setLinked(all.filter((e) => e.transaction !== null));
      const taken = new Set(all.map((e) => e.transaction?.id).filter(Boolean));
      setPurchases(txs.filter((t) => !taken.has(t.id)));
    } catch (e) {
      setError(errorText(e));
    }
  };

  useEffect(() => {
    load();
  }, []);

  const act = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
      await load();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const linkSelected = () =>
    act(async () => {
      for (const s of suggestions.filter((s) => selected.has(s.expense_id))) {
        await db.linkShared(s.expense_id, s.transaction_id);
      }
    });

  const suggested = new Set(suggestions.map((s) => s.expense_id));
  const unmatched = (waiting ?? []).filter((e) => !suggested.has(e.id));

  return (
    <div>
      <PageHeader
        title="Reconcile"
        subtitle="Link shared expenses you paid to the card charge that paid them, so the charge counts as your share."
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Stat label="Not counted yet" value={waiting?.length ?? "—"} caption="Shared expenses you paid, not linked" />
        <Stat label="Suggested matches" value={suggestions.length} caption="Card charges that look like them" />
        <Stat label="Linked" value={linked.length} caption="Counting as your share" />
      </div>

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

      <Card className="p-6 mb-6">
        <CardTitle
          actions={
            suggestions.length > 0 && (
              <button className={buttonPrimary} onClick={linkSelected} disabled={busy || selected.size === 0}>
                Link selected
              </button>
            )
          }
        >
          Suggested matches
        </CardTitle>
        {suggestions.length === 0 ? (
          <p className="text-sm text-muted">No strong matches right now.</p>
        ) : (
          <ul className="space-y-2">
            {suggestions.map((s) => (
              <li key={s.expense_id}>
                <label className="flex cursor-pointer flex-wrap items-center gap-4 rounded-xl border border-line px-4 py-3 hover:bg-surface-muted/50">
                  <input
                    type="checkbox"
                    checked={selected.has(s.expense_id)}
                    onChange={() =>
                      setSelected((set) => {
                        const next = new Set(set);
                        if (next.has(s.expense_id)) next.delete(s.expense_id);
                        else next.add(s.expense_id);
                        return next;
                      })
                    }
                  />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-ink">{s.transaction.description}</p>
                    <p className="text-sm text-muted">
                      Card {formatMoney(s.transaction.amount_cents)} on {s.transaction.date} ↔ {s.expense.description}{" "}
                      {formatMoney(s.expense.total_cents)} on {s.expense.date}
                    </p>
                  </div>
                  <span className="rounded-full bg-surface-muted px-2.5 py-0.5 text-xs text-ink-soft">{s.reason}</span>
                </label>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {unmatched.length > 0 && (
        <Card className="p-6 mb-6">
          <CardTitle>No match found</CardTitle>
          <p className="mb-3 text-sm text-muted">
            Pick the card charge yourself, or say it was paid outside your tracked accounts (cash, or a card you don't import).
          </p>
          <ul className="space-y-2">
            {unmatched.map((e) => (
              <ManualLink key={e.id} expense={e} purchases={purchases} busy={busy}
                onLink={(txId) => act(() => db.linkShared(e.id, txId))}
                onStandalone={() => act(() => db.setStandalone(e.id, true))} />
            ))}
          </ul>
        </Card>
      )}

      <Card className="p-6">
        <CardTitle>Already linked</CardTitle>
        {linked.length === 0 ? (
          <p className="text-sm text-muted">Nothing linked yet.</p>
        ) : (
          <ul className="space-y-2">
            {linked.map((e) => (
              <li key={e.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-line px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-ink">{e.transaction!.description}</p>
                  <p className="text-sm text-muted">
                    {e.description} · Card {formatMoney(e.transaction!.amount_cents)} · Your share {formatMoney(e.your_share_cents)}
                  </p>
                </div>
                <button className={buttonGhost} disabled={busy} onClick={() => act(() => db.linkShared(e.id, null))}>Unlink</button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <p className="mt-6 text-sm text-muted">
        Need to import Splitwise first?{" "}
        <button onClick={onImportSplitwise} className="font-medium text-ink underline underline-offset-4">Import CSV</button>
      </p>
    </div>
  );
}

function ManualLink({ expense, purchases, busy, onLink, onStandalone }: {
  expense: SharedExpense;
  purchases: Transaction[];
  busy: boolean;
  onLink: (transactionId: number) => void;
  onStandalone: () => void;
}) {
  const [choice, setChoice] = useState("");
  // Charges within two weeks of the expense, closest amount first.
  const nearby = purchases
    .filter((t) => daysApart(t.date, expense.date) <= 14)
    .sort((a, b) => Math.abs(a.amount_cents - expense.total_cents) - Math.abs(b.amount_cents - expense.total_cents))
    .slice(0, 20);
  return (
    <li className="flex flex-wrap items-center gap-3 rounded-xl border border-line px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="font-medium text-ink">{expense.description}</p>
        <p className="text-sm text-muted">
          {expense.date} · {formatMoney(expense.total_cents)} · Your share {formatMoney(expense.your_share_cents)}
        </p>
      </div>
      <select value={choice} onChange={(e) => setChoice(e.target.value)} className={`max-w-xs ${field}`} aria-label="Card charge">
        <option value="">{nearby.length ? "Choose the card charge…" : "No card charges nearby"}</option>
        {nearby.map((t) => (
          <option key={t.id} value={t.id}>
            {t.date} · {t.description} · {formatMoney(t.amount_cents)}
          </option>
        ))}
      </select>
      <button className={buttonPrimary} disabled={busy || !choice} onClick={() => onLink(Number(choice))}>Link</button>
      <button className={buttonGhost} disabled={busy} onClick={onStandalone}>Paid outside my accounts</button>
    </li>
  );
}
