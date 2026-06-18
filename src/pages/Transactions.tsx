import { useEffect, useState } from "react";
import { db, Transaction } from "../lib/db";
import { CATEGORIES, categoryColor } from "../lib/categories";

export function Transactions() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);

  useEffect(() => {
    db.getTransactions().then(setTransactions);
  }, []);

  const handleOverride = async (txId: number, category: string) => {
    await db.overrideCategory(txId, category);
    setTransactions((prev) =>
      prev.map((t) =>
        t.id === txId
          ? { ...t, manual_category: category, manually_overridden: true }
          : t
      )
    );
    setEditingId(null);
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold text-slate-900 mb-4">
        Transactions
      </h1>
      {transactions.length === 0 ? (
        <p className="text-sm text-slate-500">No transactions yet.</p>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-200 bg-slate-50">
                <th className="py-3 px-4">Date</th>
                <th className="py-3 px-4">Description</th>
                <th className="py-3 px-4">Amount</th>
                <th className="py-3 px-4">Category</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((tx) => {
                const displayCat =
                  tx.manual_category ?? tx.category ?? "Other";
                return (
                  <tr
                    key={tx.id}
                    className="border-b border-slate-100 hover:bg-slate-50"
                  >
                    <td className="py-2.5 px-4 text-slate-500">{tx.date}</td>
                    <td className="py-2.5 px-4 max-w-xs truncate text-slate-800">
                      {tx.description}
                    </td>
                    <td className="py-2.5 px-4 font-medium text-slate-900">
                      ${tx.amount.toFixed(2)}
                    </td>
                    <td className="py-2.5 px-4">
                      {editingId === tx.id ? (
                        <select
                          autoFocus
                          defaultValue={displayCat}
                          onChange={(e) =>
                            handleOverride(tx.id!, e.target.value)
                          }
                          onBlur={() => setEditingId(null)}
                          className="border border-slate-300 rounded px-2 py-1 text-sm"
                        >
                          {CATEGORIES.map((c) => (
                            <option key={c.name} value={c.name}>
                              {c.icon} {c.name}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <span
                          onClick={() => setEditingId(tx.id!)}
                          className="cursor-pointer px-2.5 py-1 rounded-full text-white text-xs"
                          style={{ backgroundColor: categoryColor(displayCat) }}
                        >
                          {displayCat}
                          {tx.manually_overridden && " ✏️"}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
