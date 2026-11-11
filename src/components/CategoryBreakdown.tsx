import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { categoryColor } from "../lib/categories";
import { formatMoney } from "../lib/reference";

/** Spending per Category as a donut and a ranked list. Negative Categories
 * (more Refunds than Purchases) are listed but left out of the donut. */
export function CategoryBreakdown({ categories }: { categories: { category: string; cents: number }[] }) {
  const ranked = [...categories].sort((a, b) => b.cents - a.cents);
  const total = ranked.reduce((sum, c) => sum + c.cents, 0);
  const slices = ranked.filter((c) => c.cents > 0).map((c) => ({ name: c.category, value: c.cents }));

  return (
    <div className="grid grid-cols-1 md:grid-cols-[220px_1fr] gap-6 items-center">
      <div className="relative h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={slices}
              innerRadius={56}
              outerRadius={92}
              dataKey="value"
              stroke="var(--color-surface)"
              strokeWidth={slices.length > 1 ? 2 : 0}
              startAngle={90}
              endAngle={-270}
              isAnimationActive={false}
            >
              {slices.map(({ name }) => (
                <Cell key={name} fill={categoryColor(name)} />
              ))}
            </Pie>
            <Tooltip
              formatter={(v) => formatMoney(Number(v ?? 0))}
              contentStyle={{ background: "var(--color-surface)", border: "1px solid var(--color-line)", borderRadius: 8 }}
              itemStyle={{ color: "var(--color-ink)" }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="text-xs text-muted">Total</span>
          <span className="text-sm font-semibold text-ink tabular-nums">{formatMoney(total)}</span>
        </div>
      </div>

      <ul className="space-y-2">
        {ranked.map(({ category, cents }) => (
          <li key={category} className="flex items-center gap-3 rounded-lg border border-line px-4 py-2.5">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: categoryColor(category) }} />
            <span className="flex-1 truncate text-sm text-ink">{category}</span>
            {total > 0 && cents > 0 && (
              <span className="text-xs text-faint tabular-nums">{Math.round((cents / total) * 100)}%</span>
            )}
            <span className={`text-sm font-semibold tabular-nums ${cents < 0 ? "text-emerald-700 dark:text-emerald-400" : "text-ink"}`}>
              {formatMoney(cents)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
