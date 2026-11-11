import { useEffect, useState } from "react";
import { BudgetLine, db } from "../lib/db";
import { categoryColor } from "../lib/categories";
import { formatMoney, useReference } from "../lib/reference";
import { monthLabel, thisMonth } from "../lib/month";
import { MonthPicker } from "../components/MonthPicker";
import { Card, CardTitle, PageHeader, Stat, field } from "../components/ui";

/** "$1,234.5" → 123450; blank or zero → null (no Budget); anything else → undefined (invalid). */
function parseDollars(text: string): number | null | undefined {
  const cleaned = text.replace(/[$,\s]/g, "");
  if (cleaned === "") return null;
  if (!/^\d+(\.\d{0,2})?$/.test(cleaned)) return undefined;
  const cents = Math.round(Number(cleaned) * 100);
  return cents === 0 ? null : cents;
}

const dollars = (cents: number | null) => (cents == null ? "" : (cents / 100).toFixed(2).replace(/\.00$/, ""));

export function Budgets() {
  const reference = useReference();
  const [month, setMonth] = useState(thisMonth);
  const [lines, setLines] = useState<BudgetLine[] | null>(null);
  const [extra, setExtra] = useState<string[]>([]); // Categories added to the table but not yet budgeted
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const load = () =>
    db.getBudgets(month).then(setLines, (e) => setError(e instanceof Error ? e.message : String(e)));

  useEffect(() => {
    setLines(null);
    setExtra([]);
    load();
  }, [month]);

  const save = async (category: string, cents: number | null) => {
    setError(null);
    try {
      await db.setBudget(month, category, cents);
      await load();
      setSaved(category);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const rows: BudgetLine[] = [
    ...(lines ?? []),
    ...extra.filter((c) => !lines?.some((l) => l.category === c)).map((category) => ({ category, budget_cents: null, spent_cents: 0 })),
  ];
  const budgeted = rows.filter((l) => l.budget_cents != null);
  const planned = budgeted.reduce((sum, l) => sum + (l.budget_cents ?? 0), 0);
  const spentInBudgets = budgeted.reduce((sum, l) => sum + l.spent_cents, 0);
  const unplanned = rows.filter((l) => l.budget_cents == null).reduce((sum, l) => sum + Math.max(0, l.spent_cents), 0);
  const addable = (reference?.categories ?? []).filter((c) => !rows.some((l) => l.category === c));

  return (
    <div>
      <PageHeader
        title="Budgeting"
        subtitle="Plan monthly category budgets and compare them against your spending. A budget carries forward until you change it."
        actions={<MonthPicker month={month} onChange={setMonth} />}
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Stat label="Planned" value={formatMoney(planned)} caption={`Across ${budgeted.length} ${budgeted.length === 1 ? "category" : "categories"}`} />
        <Stat
          label="Remaining"
          value={formatMoney(planned - spentInBudgets)}
          tone={planned - spentInBudgets < 0 ? "bad" : undefined}
          caption={`${formatMoney(spentInBudgets)} spent in budgeted categories`}
        />
        <Stat label="Unplanned spending" value={formatMoney(unplanned)} caption="In categories without a budget" />
      </div>

      <Card className="p-6">
        <CardTitle
          actions={
            <select
              value=""
              onChange={(e) => e.target.value && setExtra((x) => [...x, e.target.value])}
              className={field}
              aria-label="Add a category"
            >
              <option value="">Add a category…</option>
              {addable.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          }
        >
          Monthly budget plan
        </CardTitle>

        {error && <p className="mb-3 text-sm text-red-600 dark:text-red-400">{error}</p>}

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted bg-surface-muted">
                <th className="py-3 px-4 font-medium rounded-l-lg">Category</th>
                <th className="py-3 px-4 font-medium">Planned</th>
                <th className="py-3 px-4 font-medium">Spent</th>
                <th className="py-3 px-4 font-medium rounded-r-lg">Remaining</th>
              </tr>
            </thead>
            <tbody>
              {lines === null ? (
                <tr><td colSpan={4} className="py-6 px-4 text-muted">Loading…</td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan={4} className="py-6 px-4 text-muted">No spending or budgets in {monthLabel(month)} yet. Add a category to plan one.</td></tr>
              ) : (
                rows.map((line) => (
                  <BudgetRow key={line.category} line={line} saved={saved === line.category} onSave={save} />
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="mt-4 border-t border-line pt-4 text-sm text-muted">
          Total planned: <span className="font-semibold text-ink tabular-nums">{formatMoney(planned)}</span>
          <span className="ml-3 text-xs text-faint">Changes save as you go. Empty a budget to remove it from this month on.</span>
        </div>
      </Card>
    </div>
  );
}

function BudgetRow({ line, saved, onSave }: {
  line: BudgetLine;
  saved: boolean;
  onSave: (category: string, cents: number | null) => void;
}) {
  const remaining = line.budget_cents == null ? null : line.budget_cents - line.spent_cents;
  const share = line.budget_cents ? Math.max(0, line.spent_cents) / line.budget_cents : 0;
  return (
    <tr className="border-b border-line-soft last:border-0">
      <td className="py-3 px-4">
        <span className="inline-flex items-center gap-2.5 font-medium text-ink">
          <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: categoryColor(line.category) }} />
          {line.category}
        </span>
      </td>
      <td className="py-3 px-4">
        <AmountInput key={line.budget_cents} initial={line.budget_cents} saved={saved} onCommit={(c) => onSave(line.category, c)} />
      </td>
      <td className="py-3 px-4 tabular-nums text-ink-soft">{formatMoney(line.spent_cents)}</td>
      <td className="py-3 px-4 min-w-40">
        {remaining == null ? (
          <span className="text-faint">No budget</span>
        ) : (
          <>
            <span className={`tabular-nums ${remaining < 0 ? "text-red-600 dark:text-red-400" : "text-ink-soft"}`}>
              {remaining < 0 ? `${formatMoney(-remaining)} over` : formatMoney(remaining)}
            </span>
            <div className="mt-1.5 h-1.5 rounded-full bg-surface-muted overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{ width: `${Math.min(share, 1) * 100}%`, background: share > 1 ? "#dc2626" : categoryColor(line.category) }}
              />
            </div>
          </>
        )}
      </td>
    </tr>
  );
}

/** A dollar amount saved on Enter or when it loses focus. */
function AmountInput({ initial, saved, onCommit }: {
  initial: number | null;
  saved: boolean;
  onCommit: (cents: number | null) => void;
}) {
  const [text, setText] = useState(dollars(initial));
  const parsed = parseDollars(text);
  const commit = () => {
    if (parsed !== undefined && parsed !== initial) onCommit(parsed);
  };
  return (
    <span className="inline-flex items-center gap-2">
      <input
        value={text}
        inputMode="decimal"
        aria-label="Planned amount"
        aria-invalid={parsed === undefined}
        placeholder="0"
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
        className={`w-28 tabular-nums ${field} ${parsed === undefined ? "border-red-500" : ""}`}
      />
      {saved && <span className="text-xs text-faint">Saved</span>}
    </span>
  );
}
