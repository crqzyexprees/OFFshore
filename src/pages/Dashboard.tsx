import { useEffect, useState } from "react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { PieChart as PieIcon } from "lucide-react";
import { BudgetLine, db, Spending } from "../lib/db";
import { formatMoney } from "../lib/reference";
import { monthLabel, shiftMonth, thisMonth } from "../lib/month";
import { MonthPicker } from "../components/MonthPicker";
import { CategoryBreakdown } from "../components/CategoryBreakdown";
import { Card, CardTitle, EmptyState, PageHeader, Stat } from "../components/ui";

const HISTORY = 6; // months in the month-over-month chart

// Spending is Purchases minus Refunds, so a Category (or a month) can be negative.
const totalOf = (s: Spending) => s.categories.reduce((sum, c) => sum + c.cents, 0);
const shortMonth = (month: string) => monthLabel(month).split(" ")[0].slice(0, 3);

/** Percent change from `previous`, or null when there's nothing to compare with. */
function change(current: number, previous: number): number | null {
  return previous > 0 ? ((current - previous) / previous) * 100 : null;
}

export function Dashboard({ onImport }: { onImport: () => void }) {
  const [month, setMonth] = useState(thisMonth);
  const [history, setHistory] = useState<{ month: string; spending: Spending }[] | null>(null);
  const [budgets, setBudgets] = useState<BudgetLine[]>([]);

  useEffect(() => {
    const months = Array.from({ length: HISTORY }, (_, i) => shiftMonth(month, i - HISTORY + 1));
    Promise.all(months.map((m) => db.getSpending(m).then((spending) => ({ month: m, spending })))).then(setHistory);
    db.getBudgets(month).then(setBudgets, () => setBudgets([]));
  }, [month]);

  const current = history?.[HISTORY - 1];
  const previous = history?.[HISTORY - 2];
  const total = current ? totalOf(current.spending) : 0;
  const previousTotal = previous ? totalOf(previous.spending) : 0;
  const pct = change(total, previousTotal);
  const budgeted = budgets.filter((b) => b.budget_cents != null);
  const budgetTotal = budgeted.reduce((sum, b) => sum + (b.budget_cents ?? 0), 0);
  const budgetLeft = budgetTotal - budgeted.reduce((sum, b) => sum + b.spent_cents, 0);

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle="Overview of your spending across every account."
        actions={<MonthPicker month={month} onChange={setMonth} latest={thisMonth()} />}
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Stat
          label="Spending"
          value={formatMoney(total)}
          caption={`For ${monthLabel(month)}${pct === null ? "" : ` · ${pct > 0 ? "+" : ""}${pct.toFixed(1)}% vs last month`}`}
        />
        <Stat
          label="Budget left"
          value={budgeted.length ? formatMoney(budgetLeft) : "—"}
          tone={budgeted.length && budgetLeft < 0 ? "bad" : undefined}
          caption={budgeted.length ? `Of ${formatMoney(budgetTotal)} budgeted` : "No Budgets set for this month"}
        />
        <Stat
          label="Cash withdrawn"
          value={formatMoney(current?.spending.withdrawn_cents ?? 0)}
          caption="ATM withdrawals, not counted as spending"
        />
      </div>

      <Card className="p-6 mb-6">
        <CardTitle>Month over month</CardTitle>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div className="rounded-xl border border-line p-4">
            <p className="text-sm text-muted">{monthLabel(month)}</p>
            <p className="text-2xl font-bold text-ink tabular-nums mt-2">{formatMoney(total)}</p>
            <p className="text-sm text-muted mt-1">Purchases minus refunds; transfers and payments excluded</p>
          </div>
          <div className="rounded-xl border border-line p-4">
            <p className="text-sm text-muted">{monthLabel(shiftMonth(month, -1))}</p>
            <p className="text-2xl font-bold text-ink tabular-nums mt-2">{formatMoney(previousTotal)}</p>
            <p className={`text-sm mt-1 ${pct === null ? "text-muted" : pct > 0 ? "text-red-600 dark:text-red-400" : "text-emerald-700 dark:text-emerald-400"}`}>
              {pct === null ? "Nothing to compare with" : `${pct > 0 ? "Up" : "Down"} ${Math.abs(pct).toFixed(1)}% this month`}
            </p>
          </div>
        </div>
        <div className="h-44">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={(history ?? []).map((h) => ({ month: h.month, cents: Math.max(0, totalOf(h.spending)) }))}>
              <XAxis
                dataKey="month"
                tickFormatter={shortMonth}
                tickLine={false}
                axisLine={false}
                tick={{ fill: "var(--color-muted)", fontSize: 12 }}
              />
              <Tooltip
                cursor={{ fill: "var(--color-surface-muted)" }}
                formatter={(v) => [formatMoney(Number(v ?? 0)), "Spending"]}
                labelFormatter={(m) => monthLabel(String(m))}
                contentStyle={{ background: "var(--color-surface)", border: "1px solid var(--color-line)", borderRadius: 8 }}
                itemStyle={{ color: "var(--color-ink)" }}
              />
              <Bar dataKey="cents" radius={[6, 6, 0, 0]} maxBarSize={56} isAnimationActive={false}>
                {(history ?? []).map((h) => (
                  <Cell key={h.month} fill={h.month === month ? "var(--color-accent)" : "var(--color-field)"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card className="p-6">
        <CardTitle>Spending by category</CardTitle>
        {current && current.spending.categories.length > 0 ? (
          <CategoryBreakdown categories={current.spending.categories} />
        ) : (
          <EmptyState
            icon={<PieIcon size={36} />}
            title={`No spending in ${monthLabel(month)}`}
            hint="Import a statement that covers this month, or step back to an earlier one."
            action={
              <button onClick={onImport} className="text-sm font-medium text-ink underline underline-offset-4 hover:no-underline">
                Upload a statement
              </button>
            }
          />
        )}
      </Card>
    </div>
  );
}
