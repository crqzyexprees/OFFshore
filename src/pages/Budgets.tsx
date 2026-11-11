import { useEffect, useState } from "react";
import { Target } from "lucide-react";
import { BudgetLine, db } from "../lib/db";
import { categoryColor, CategoryIcon } from "../lib/categories";
import { formatMoney, useReference } from "../lib/reference";
import { monthLabel, thisMonth } from "../lib/month";
import { MonthPicker } from "../components/MonthPicker";
import { Card, EmptyState, PageHeader, buttonGhost, field } from "../components/ui";

/** "$1,234.5" → 123450; blank → null; anything else → undefined (not a valid amount). */
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
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState("");

  const load = () =>
    db.getBudgets(month).then(setLines, (e) => setError(e instanceof Error ? e.message : String(e)));

  useEffect(() => {
    setLines(null);
    load();
  }, [month]);

  const save = async (category: string, cents: number | null) => {
    setError(null);
    try {
      await db.setBudget(month, category, cents);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const budgeted = (lines ?? []).filter((l) => l.budget_cents != null);
  const unbudgeted = (lines ?? []).filter((l) => l.budget_cents == null);
  const totalBudget = budgeted.reduce((sum, l) => sum + (l.budget_cents ?? 0), 0);
  const spentInBudgets = budgeted.reduce((sum, l) => sum + l.spent_cents, 0);
  const addable = (reference?.categories ?? []).filter((c) => !budgeted.some((l) => l.category === c));

  return (
    <div className="p-6 max-w-4xl">
      <PageHeader
        title="Budgets"
        subtitle="A Budget applies from the month you set it until you change it. Empty the amount to remove it from that month on."
        actions={<MonthPicker month={month} onChange={setMonth} />}
      />

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {budgeted.length > 0 && (
        <Card className="p-4 mb-6">
          <p className="text-sm text-muted">Spent of budgeted in {monthLabel(month)}</p>
          <p className="text-3xl font-bold text-ink tabular-nums mt-1">
            {formatMoney(spentInBudgets)} <span className="text-lg font-medium text-muted">of {formatMoney(totalBudget)}</span>
          </p>
          <Bar spent={spentInBudgets} budget={totalBudget} color="#6366f1" />
        </Card>
      )}

      <Card className="divide-y divide-line">
        {lines === null ? (
          <p className="p-4 text-sm text-muted">Loading…</p>
        ) : budgeted.length === 0 ? (
          <EmptyState icon={<Target size={36} />} title="No Budgets yet"
            hint="Pick a Category below and give it a monthly amount." />
        ) : (
          budgeted.map((line) => <BudgetRow key={line.category} line={line} onSave={save} />)
        )}
        <div className="p-4 flex flex-wrap items-center gap-2">
          <select value={adding} onChange={(e) => setAdding(e.target.value)} className={field}>
            <option value="">Add a Budget for…</option>
            {addable.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          {adding && (
            <AmountInput
              key={adding}
              initial={null}
              autoFocus
              onCommit={(cents) => {
                if (cents != null) save(adding, cents).then(() => setAdding(""));
              }}
            />
          )}
        </div>
      </Card>

      {unbudgeted.length > 0 && (
        <div className="mt-6">
          <h2 className="text-sm font-medium text-ink-soft mb-2">Spending without a Budget</h2>
          <Card className="divide-y divide-line">
            {unbudgeted.map((line) => (
              <div key={line.category} className="flex items-center gap-3 px-4 py-2.5">
                <CategoryIcon name={line.category} size={24} />
                <span className="flex-1 text-sm text-ink">{line.category}</span>
                <span className="text-sm tabular-nums text-ink-soft">{formatMoney(line.spent_cents)}</span>
                <button className={buttonGhost} onClick={() => setAdding(line.category)}>Set Budget</button>
              </div>
            ))}
          </Card>
        </div>
      )}
    </div>
  );
}

function BudgetRow({ line, onSave }: { line: BudgetLine; onSave: (category: string, cents: number | null) => void }) {
  const budget = line.budget_cents ?? 0;
  const left = budget - line.spent_cents;
  return (
    <div className="px-4 py-3">
      <div className="flex items-center gap-3">
        <CategoryIcon name={line.category} size={28} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-ink">{line.category}</p>
          <p className={`text-xs tabular-nums ${left < 0 ? "text-red-600 dark:text-red-400" : "text-muted"}`}>
            {formatMoney(line.spent_cents)} spent · {left < 0 ? `${formatMoney(-left)} over` : `${formatMoney(left)} left`}
          </p>
        </div>
        <AmountInput key={line.budget_cents} initial={line.budget_cents} onCommit={(cents) => onSave(line.category, cents)} />
      </div>
      <Bar spent={line.spent_cents} budget={budget} color={categoryColor(line.category)} />
    </div>
  );
}

/** A dollar amount saved on Enter or when it loses focus; emptying it clears the Budget. */
function AmountInput({ initial, onCommit, autoFocus }: {
  initial: number | null;
  onCommit: (cents: number | null) => void;
  autoFocus?: boolean;
}) {
  const [text, setText] = useState(dollars(initial));
  const parsed = parseDollars(text);
  const commit = () => {
    if (parsed !== undefined && parsed !== initial) onCommit(parsed);
  };
  return (
    <div className="flex items-center gap-1">
      <span className="text-sm text-muted">$</span>
      <input
        value={text}
        inputMode="decimal"
        autoFocus={autoFocus}
        aria-label="Monthly budget"
        aria-invalid={parsed === undefined}
        placeholder="0"
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
        className={`w-24 text-right tabular-nums ${field} ${parsed === undefined ? "border-red-500" : ""}`}
      />
    </div>
  );
}

function Bar({ spent, budget, color }: { spent: number; budget: number; color: string }) {
  const share = budget > 0 ? Math.max(0, spent) / budget : 0;
  return (
    <div className="mt-2 h-2 rounded-full bg-surface-muted overflow-hidden" role="presentation">
      <div
        className="h-full rounded-full transition-all"
        style={{ width: `${Math.min(share, 1) * 100}%`, background: share > 1 ? "#dc2626" : color }}
      />
    </div>
  );
}
