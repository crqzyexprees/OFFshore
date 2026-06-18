import { useState } from "react";
import { db, Account } from "../lib/db";

const BANKS = [
  "Chase",
  "American Express",
  "Citi",
  "Bank of America",
  "Wells Fargo",
  "Capital One",
  "Other",
];

const COLORS = [
  "#6366f1",
  "#22c55e",
  "#f97316",
  "#ec4899",
  "#3b82f6",
  "#8b5cf6",
  "#14b8a6",
];

interface CardsProps {
  accounts: Account[];
  onChange: () => void;
}

export function Cards({ accounts, onChange }: CardsProps) {
  const [name, setName] = useState("");
  const [bank, setBank] = useState(BANKS[0]);
  const [lastFour, setLastFour] = useState("");
  const [color, setColor] = useState(COLORS[0]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    await db.addAccount({
      name: name.trim(),
      bank,
      last_four: lastFour || undefined,
      color,
    });
    setName("");
    setLastFour("");
    onChange();
  };

  const handleDelete = async (id: number) => {
    await db.deleteAccount(id);
    onChange();
  };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Cards</h1>

      <form
        onSubmit={handleAdd}
        className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 space-y-3 max-w-md"
      >
        <h2 className="text-sm font-medium text-slate-700">Add a card</h2>
        <input
          placeholder="Card nickname"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
        />
        <select
          value={bank}
          onChange={(e) => setBank(e.target.value)}
          className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
        >
          {BANKS.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>
        <input
          placeholder="Last 4 digits (optional)"
          value={lastFour}
          onChange={(e) => setLastFour(e.target.value)}
          maxLength={4}
          className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
        />
        <div className="flex gap-2">
          {COLORS.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setColor(c)}
              className={`w-6 h-6 rounded-full border-2 ${
                color === c ? "border-slate-800" : "border-transparent"
              }`}
              style={{ backgroundColor: c }}
            />
          ))}
        </div>
        <button
          type="submit"
          className="w-full bg-indigo-600 hover:bg-indigo-700 text-white py-2 rounded-lg text-sm font-medium"
        >
          Add Card
        </button>
      </form>

      <div className="space-y-2">
        {accounts.length === 0 ? (
          <p className="text-sm text-slate-500">No cards added yet.</p>
        ) : (
          accounts.map((a) => (
            <div
              key={a.id}
              className="flex items-center justify-between bg-white rounded-xl shadow-sm border border-slate-200 px-4 py-3"
            >
              <div className="flex items-center gap-3">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: a.color ?? "#6366f1" }}
                />
                <div>
                  <p className="font-medium text-slate-900">{a.name}</p>
                  <p className="text-xs text-slate-500">
                    {a.bank}
                    {a.last_four ? ` •••• ${a.last_four}` : ""}
                  </p>
                </div>
              </div>
              <button
                onClick={() => handleDelete(a.id!)}
                className="text-xs text-red-600 hover:text-red-700"
              >
                Remove
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
