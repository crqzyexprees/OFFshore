import { useEffect, useState } from "react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { db } from "../lib/db";
import { categoryColor, categoryIcon } from "../lib/categories";

export function Dashboard() {
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const [spending, setSpending] = useState<[string, number][]>([]);
  const [totalSpend, setTotal] = useState(0);

  useEffect(() => {
    db.getSpendingByCategory(month).then((data) => {
      setSpending(data);
      setTotal(data.reduce((sum, [, amt]) => sum + amt, 0));
    });
  }, [month]);

  const pieData = spending.map(([name, value]) => ({ name, value }));

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">
          Spending Overview
        </h1>
        <input
          type="month"
          value={month}
          onChange={(e) => setMonth(e.target.value)}
          className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
          <p className="text-sm text-slate-500 mb-1">Total Spent</p>
          <p className="text-3xl font-bold text-slate-900">
            ${totalSpend.toFixed(2)}
          </p>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  dataKey="value"
                >
                  {pieData.map(({ name }) => (
                    <Cell key={name} fill={categoryColor(name)} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v) =>
                    `$${Number(v ?? 0).toFixed(2)}`
                  }
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-slate-400 mt-8 text-center">
              No spending data for this month
            </p>
          )}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 overflow-y-auto max-h-80">
          {spending.length === 0 ? (
            <p className="text-sm text-slate-400">Import a statement to get started</p>
          ) : (
            spending.map(([name, total]) => (
              <div
                key={name}
                className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0"
              >
                <div className="flex items-center gap-2">
                  <span>{categoryIcon(name)}</span>
                  <span className="text-sm text-slate-700">{name}</span>
                </div>
                <div className="text-right">
                  <span className="font-medium text-slate-900">
                    ${total.toFixed(2)}
                  </span>
                  {totalSpend > 0 && (
                    <span className="text-xs text-slate-400 ml-2">
                      {((total / totalSpend) * 100).toFixed(1)}%
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
