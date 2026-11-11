import { useState } from "react";
import { CreditCard, Landmark, Trash2 } from "lucide-react";
import { db, Account, AccountKind } from "../lib/db";
import { accountKindName, bankName, useReference } from "../lib/reference";
import { Card, CardTitle, PageHeader, buttonPrimary, field } from "../components/ui";

const COLORS = [
  "#6366f1",
  "#22c55e",
  "#f97316",
  "#ec4899",
  "#3b82f6",
  "#8b5cf6",
  "#14b8a6",
];

// Presentation only: the account kinds themselves come from the backend.
const AccountKindIcon = ({ kind, size }: { kind: AccountKind; size: number }) =>
  kind === "bank" ? <Landmark size={size} /> : <CreditCard size={size} />;

interface AccountsProps {
  accounts: Account[];
  onChange: () => void;
}

export function Accounts({ accounts, onChange }: AccountsProps) {
  const reference = useReference();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<AccountKind | null>(null);
  const [bank, setBank] = useState<string | null>(null);
  const [lastFour, setLastFour] = useState("");
  const [color, setColor] = useState(COLORS[0]);
  const [error, setError] = useState<string | null>(null);

  // Until the user picks, the first of each list the backend offers.
  const chosenKind = kind ?? reference?.account_kinds[0]?.id ?? null;
  const chosenBank = bank ?? reference?.banks[0]?.id ?? null;

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !chosenKind || !chosenBank) return;
    setError(null);
    try {
      await db.addAccount({
        name: name.trim(),
        kind: chosenKind,
        bank: chosenBank,
        last_four: lastFour || undefined,
        color,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return;
    }
    setName("");
    setLastFour("");
    onChange();
  };

  const [confirming, setConfirming] = useState<number | null>(null);

  // Removing an Account removes its Statements and Transactions too.
  const handleDelete = async (id: number) => {
    setConfirming(null);
    await db.deleteAccount(id);
    onChange();
  };

  return (
    <div>
      <PageHeader title="Accounts" subtitle="The credit cards and bank accounts you upload statements for." />

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,420px)_1fr] gap-6 items-start">
      <Card className="p-6">
      <form onSubmit={handleAdd} className="space-y-3">
        <CardTitle>Add account</CardTitle>
        <input
          placeholder="Nickname"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className={`w-full ${field}`}
        />
        <div className="flex gap-2">
          {reference?.account_kinds.map((k) => (
            <button
              key={k.id}
              type="button"
              onClick={() => setKind(k.id)}
              className={`flex-1 inline-flex items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                chosenKind === k.id
                  ? "border-accent bg-accent text-accent-ink"
                  : "border-line bg-surface text-ink hover:bg-surface-muted"
              }`}
            >
              <AccountKindIcon kind={k.id} size={15} />
              {k.name}
            </button>
          ))}
        </div>
        <select
          value={chosenBank ?? ""}
          onChange={(e) => setBank(e.target.value)}
          className={`w-full ${field}`}
        >
          {reference?.banks.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
        <input
          placeholder="Last 4 digits (lets statements be matched automatically)"
          value={lastFour}
          onChange={(e) => setLastFour(e.target.value.replace(/\D/g, ""))}
          maxLength={4}
          className={`w-full ${field}`}
        />
        <div className="flex gap-2">
          {COLORS.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setColor(c)}
              aria-label={`Colour ${c}`}
              className={`w-6 h-6 rounded-full transition-transform ${
                color === c ? "ring-2 ring-offset-2 ring-offset-surface ring-ink scale-110" : "hover:scale-110"
              }`}
              style={{ backgroundColor: c }}
            />
          ))}
        </div>
        <button
          type="submit"
          className={`w-full ${buttonPrimary}`}
        >
          Add account
        </button>
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      </form>
      </Card>

      <Card className="p-6">
      <CardTitle>Your accounts</CardTitle>
      <div className="space-y-2">
        {accounts.length === 0 ? (
          <p className="text-sm text-muted">No accounts yet. Add your first card or bank account.</p>
        ) : (
          accounts.map((a) => (
            <div
              key={a.id}
              className="flex items-center justify-between rounded-xl border border-line px-4 py-3"
            >
              <div className="flex items-center gap-3">
                <div
                  className="w-9 h-9 rounded-lg flex items-center justify-center text-white"
                  style={{ backgroundColor: a.color ?? "#71717a" }}
                >
                  <AccountKindIcon kind={a.kind} size={18} />
                </div>
                <div>
                  <p className="font-medium text-ink">{a.name}</p>
                  <p className="text-xs text-muted">
                    {accountKindName(reference, a.kind)} · {bankName(reference, a.bank)}
                    {a.last_four ? ` •••• ${a.last_four}` : ""}
                  </p>
                </div>
              </div>
              {confirming === a.id ? (
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-muted">Delete it and all its transactions?</span>
                  <button
                    onClick={() => handleDelete(a.id!)}
                    className="rounded-md bg-red-600 hover:bg-red-700 text-white px-2.5 py-1 font-medium"
                  >
                    Delete
                  </button>
                  <button onClick={() => setConfirming(null)} className="rounded-md px-2.5 py-1 text-ink-soft hover:bg-surface-muted">
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setConfirming(a.id!)}
                  className="p-1.5 rounded-md text-faint hover:text-red-600 dark:hover:text-red-400 hover:bg-surface-muted"
                  aria-label={`Remove ${a.name}`}
                  title="Remove account"
                >
                  <Trash2 size={16} />
                </button>
              )}
            </div>
          ))
        )}
      </div>
      </Card>
      </div>
    </div>
  );
}
