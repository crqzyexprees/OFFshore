import { useEffect, useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { ArrowDownRight, ArrowUpRight, Banknote, PieChart as PieIcon } from "lucide-react";
import { db, Spending } from "../lib/db";
import { categoryColor, CategoryIcon } from "../lib/categories";
import { formatMoney } from "../lib/reference";
import { Card, EmptyState, PageHeader } from "../components/ui";
import { MonthPicker } from "../components/MonthPicker";
import { monthLabel, shiftMonth, thisMonth } from "../lib/month";

const EMPTY: Spending = { categories: [], withdrawn_cents: 0 };

// Spending is Purchases minus Refunds, so a Category can be negative.
const totalOf = (s: Spending) => s.categories.reduce((sum, c) => sum + c.cents, 0);

export function Dashboard({ onImport }: { onImport: () => void }) {
  const [month, setMonth] = useState(thisMonth);
  const [spending, setSpending] = useState<Spending>(EMPTY);
  const [previous, setPrevious] = useState<Spending>(EMPTY);

  useEffect(() => {
    db.getSpending(month).then(setSpending);
    db.getSpending(shiftMonth(month, -1)).then(setPrevious);
  }, [month]);

  const total = totalOf(spending);
  const previousTotal = totalOf(previous);
  const ranked = [...spending.categories].sort((a, b) => b.cents - a.cents);
  const largest = Math.max(...ranked.map((c) => c.cents), 1);
  const pieData = ranked.filter((c) => c.cents > 0).map((c) => ({ name: c.category, value: c.cents }));

  return (
    <div className="p-6 max-w-6xl">
      <PageHeader
        title="Spending"
        actions={<MonthPicker month={month} onChange={setMonth} latest={thisMonth()} />}
      />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <Card className="p-4">
          <p className="text-sm text-muted">Spent this month</p>
          <p className="text-3xl font-bold text-ink tabular-nums mt-1">{formatMoney(total)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted">Compared with {monthLabel(shiftMonth(month, -1)).split(" ")[0]}</p>
          <Change current={total} previous={previousTotal} />
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted flex items-center gap-1.5">
            <Banknote size={14} /> Cash withdrawn (ATM)
          </p>
          <p className="text-2xl font-semibold text-ink-soft tabular-nums mt-1">{formatMoney(spending.withdrawn_cents)}</p>
        </Card>
      </div>

      {ranked.length === 0 ? (
        <Card>
          <EmptyState
            icon={<PieIcon size={36} />}
            title={`No spending in ${monthLabel(month)}`}
            hint="Import a statement that covers this month, or step back to an earlier one."
            action={
              <button onClick={onImport} className="text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:underline">
                Import a statement →
              </button>
            }
          />
        </Card>
      ) : (
        <Card className="p-5 grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-6 items-center">
          <div className="relative h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  innerRadius={72}
                  outerRadius={110}
                  dataKey="value"
                  stroke="var(--color-surface)"
                  strokeWidth={pieData.length > 1 ? 2 : 0}
                  startAngle={90}
                  endAngle={-270}
                >
                  {pieData.map(({ name }) => (
                    <Cell key={name} fill={categoryColor(name)} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v) => formatMoney(Number(v ?? 0))}
                  contentStyle={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-line)",
                    borderRadius: 8,
                  }}
                  itemStyle={{ color: "var(--color-ink)" }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <span className="text-xs text-muted">
                {pieData.length} {pieData.length === 1 ? "category" : "categories"}
              </span>
              <span className="text-lg font-semibold text-ink tabular-nums">{formatMoney(total)}</span>
            </div>
          </div>

          <ul className="space-y-3">
            {ranked.map(({ category, cents }) => (
              <li key={category} className="flex items-center gap-3">
                <CategoryIcon name={category} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-sm text-ink truncate">{category}</span>
                    <span className="text-sm tabular-nums whitespace-nowrap">
                      <span className={`font-medium ${cents < 0 ? "text-emerald-700 dark:text-emerald-400" : "text-ink"}`}>
                        {formatMoney(cents)}
                      </span>
                      {total > 0 && cents > 0 && (
                        <span className="text-xs text-faint ml-2 inline-block w-11 text-right">
                          {((cents / total) * 100).toFixed(0)}%
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-surface-muted mt-1.5 overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${Math.max(0, (cents / largest) * 100)}%`, backgroundColor: categoryColor(category) }}
                    />
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

/** Month-over-month change in Spending; more spending is shown as the "bad" direction. */
function Change({ current, previous }: { current: number; previous: number }) {
  if (previous <= 0) {
    return <p className="text-2xl font-semibold text-faint mt-1">—</p>;
  }
  const diff = current - previous;
  const pct = (diff / previous) * 100;
  const up = diff > 0;
  const Arrow = up ? ArrowUpRight : ArrowDownRight;
  return (
    <div className="mt-1">
      <p
        className={`text-2xl font-semibold tabular-nums flex items-center gap-1 ${
          up ? "text-red-600 dark:text-red-400" : "text-emerald-700 dark:text-emerald-400"
        }`}
      >
        <Arrow size={22} />
        {Math.abs(pct).toFixed(0)}%
      </p>
      <p className="text-xs text-muted tabular-nums">
        {up ? "+" : "−"}
        {formatMoney(Math.abs(diff))} vs {formatMoney(previous)}
      </p>
    </div>
  );
}
