import { useEffect, useState } from "react";
import { Trash2, Users } from "lucide-react";
import { db, Group, NewSharedExpense, Person, Settlement, SharedExpense } from "../lib/db";
import { categoryColor } from "../lib/categories";
import { formatMoney, useReference } from "../lib/reference";
import { parseDollars, splitEvenly, today } from "../lib/money";
import { SplitwiseImport } from "../components/SplitwiseImport";
import { Card, CardTitle, EmptyState, PageHeader, buttonGhost, buttonPrimary, field } from "../components/ui";

const label = "mb-2 block text-sm font-medium text-ink-soft";
const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e));

export function Shared({ onReconcile, onPeople, startImport = false, onImportClosed }: {
  onReconcile: () => void;
  onPeople: () => void;
  startImport?: boolean;
  onImportClosed?: () => void;
}) {
  const [people, setPeople] = useState<Person[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [expenses, setExpenses] = useState<SharedExpense[] | null>(null);
  const [settlements, setSettlements] = useState<Settlement[]>([]);
  const [importing, setImporting] = useState(startImport);
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    Promise.all([db.getPeople(), db.getGroups(), db.getShared(), db.getSettlements()]).then(
      ([p, g, e, s]) => {
        setPeople(p);
        setGroups(g);
        setExpenses(e);
        setSettlements(s);
      },
      (e) => setError(errorText(e))
    );

  useEffect(() => {
    load();
  }, []);

  const act = async (action: () => Promise<unknown>) => {
    setError(null);
    try {
      await action();
      await load();
    } catch (e) {
      setError(errorText(e));
    }
  };

  if (importing) {
    return <SplitwiseImport onDone={() => { setImporting(false); onImportClosed?.(); load(); }} onReconcile={onReconcile} />;
  }

  return (
    <div>
      <PageHeader
        title="Shared expenses"
        subtitle="Costs you split with other people. Only your share counts as your spending."
        actions={<button className={buttonGhost} onClick={() => setImporting(true)}>Import from Splitwise</button>}
      />

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

      <ExpenseForm people={people} groups={groups} onPeople={onPeople} onSaved={load} />

      <Balances people={people} onSettle={(id) => act(() => db.settleUp(id, today()))} />

      <Card className="p-6 mb-6">
        <CardTitle>All shared expenses</CardTitle>
        {expenses === null ? (
          <p className="text-sm text-muted">Loading…</p>
        ) : expenses.length === 0 ? (
          <EmptyState icon={<Users size={36} />} title="No shared expenses yet"
            hint="Add one above, or import your Splitwise history." />
        ) : (
          <ul className="space-y-2">
            {expenses.map((e) => (
              <ExpenseRow key={e.id} expense={e} onReconcile={onReconcile} onDelete={() => act(() => db.deleteShared(e.id))} />
            ))}
          </ul>
        )}
      </Card>

      {settlements.length > 0 && (
        <Card className="p-6">
          <CardTitle>Settlements</CardTitle>
          <ul className="space-y-2">
            {settlements.map((s) => (
              <li key={s.id} className="flex items-center gap-3 rounded-xl border border-line px-4 py-3 text-sm">
                <span className="w-24 shrink-0 tabular-nums text-muted">{s.date}</span>
                <span className="flex-1 text-ink">
                  {s.direction === "from_them" ? `${s.name} paid you` : `You paid ${s.name}`}
                  {s.note && <span className="text-muted"> · {s.note}</span>}
                </span>
                <span className="font-semibold tabular-nums text-ink">{formatMoney(s.cents)}</span>
                <button onClick={() => act(() => db.deleteSettlement(s.id))} aria-label="Delete settlement"
                  className="rounded-md p-1.5 text-faint hover:bg-surface-muted hover:text-red-600">
                  <Trash2 size={15} />
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

function ExpenseRow({ expense: e, onReconcile, onDelete }: { expense: SharedExpense; onReconcile: () => void; onDelete: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const status = e.paid_by !== null
    ? null
    : e.transaction
      ? <span className="rounded-full bg-surface-muted px-2.5 py-0.5 text-xs text-ink-soft">Linked to {e.transaction.description}</span>
      : e.standalone
        ? <span className="rounded-full bg-surface-muted px-2.5 py-0.5 text-xs text-ink-soft">Paid outside your accounts</span>
        : <button onClick={onReconcile} className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs text-amber-800 hover:underline dark:bg-amber-950/60 dark:text-amber-300">
            Not counted yet · link on Reconcile
          </button>;
  return (
    <li className="rounded-xl border border-line px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className="w-24 shrink-0 text-sm tabular-nums text-muted">{e.date}</span>
        <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: categoryColor(e.category) }} title={e.category} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-ink">{e.description}</p>
          <p className="text-sm text-muted">
            {e.paid_by_name ? `${e.paid_by_name} paid` : "You paid"} {formatMoney(e.total_cents)}
            {e.shares.length > 0 && ` · ${e.shares.map((s) => `${s.name} ${formatMoney(s.cents)}`).join(", ")}`}
            {e.group_name && ` · ${e.group_name}`}
            {e.from_splitwise && " · Splitwise"}
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs text-muted">Your share</p>
          <p className="font-semibold tabular-nums text-ink">{formatMoney(e.your_share_cents)}</p>
        </div>
        {confirming ? (
          <span className="flex items-center gap-2 text-sm">
            <button onClick={onDelete} className="rounded-md bg-red-600 px-2.5 py-1 font-medium text-white hover:bg-red-700">Delete</button>
            <button onClick={() => setConfirming(false)} className="rounded-md px-2.5 py-1 text-ink-soft hover:bg-surface-muted">Cancel</button>
          </span>
        ) : (
          <button onClick={() => setConfirming(true)} aria-label={`Delete ${e.description}`}
            className="rounded-md p-1.5 text-faint hover:bg-surface-muted hover:text-red-600 dark:hover:text-red-400">
            <Trash2 size={16} />
          </button>
        )}
      </div>
      {status && <div className="mt-2 pl-27">{status}</div>}
    </li>
  );
}

function Balances({ people, onSettle }: { people: Person[]; onSettle: (id: number) => void }) {
  const [order, setOrder] = useState<"amount" | "name">("amount");
  const open = people
    .filter((p) => p.balance_cents !== 0)
    .sort((a, b) => (order === "name" ? a.name.localeCompare(b.name) : Math.abs(b.balance_cents) - Math.abs(a.balance_cents)));
  const owedToYou = open.filter((p) => p.balance_cents > 0).reduce((s, p) => s + p.balance_cents, 0);
  const youOwe = open.filter((p) => p.balance_cents < 0).reduce((s, p) => s - p.balance_cents, 0);
  return (
    <Card className="p-6 mb-6">
      <CardTitle
        actions={
          <select value={order} onChange={(e) => setOrder(e.target.value as "amount" | "name")} className={field} aria-label="Sort balances">
            <option value="amount">Largest first</option>
            <option value="name">By name</option>
          </select>
        }
      >
        Running balances
      </CardTitle>
      {open.length === 0 ? (
        <p className="text-sm text-muted">No outstanding balances right now.</p>
      ) : (
        <>
          <p className="mb-4 text-sm text-muted">
            Owed to you <span className="font-semibold text-emerald-700 dark:text-emerald-400">{formatMoney(owedToYou)}</span>
            {" · "}You owe <span className="font-semibold text-red-600 dark:text-red-400">{formatMoney(youOwe)}</span>
          </p>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {open.map((p) => (
              <div key={p.id} className="rounded-xl border border-line p-5">
                <p className="text-sm text-muted">{p.name}</p>
                <p className={`mt-1 text-2xl font-bold tabular-nums ${p.balance_cents > 0 ? "text-emerald-700 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>
                  {p.balance_cents > 0 ? `Owes you ${formatMoney(p.balance_cents)}` : `You owe ${formatMoney(-p.balance_cents)}`}
                </p>
                <button className={`mt-3 ${buttonPrimary}`} onClick={() => onSettle(p.id)}>Mark settled</button>
              </div>
            ))}
          </div>
        </>
      )}
    </Card>
  );
}

type Payer = "me" | "them";
type SplitMode = "equal" | "custom";

function ExpenseForm({ people, groups, onPeople, onSaved }: {
  people: Person[];
  groups: Group[];
  onPeople: () => void;
  onSaved: () => void;
}) {
  const reference = useReference();
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(today);
  const [category, setCategory] = useState("Other");
  const [groupId, setGroupId] = useState<number | null>(null);
  const [payer, setPayer] = useState<Payer>("me");
  const [paidBy, setPaidBy] = useState<number | null>(null);
  const [withIds, setWithIds] = useState<number[]>([]);
  const [mode, setMode] = useState<SplitMode>("equal");
  const [custom, setCustom] = useState<Record<number, string>>({});
  const [yourShareText, setYourShareText] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const total = parseDollars(amount) ?? 0;
  // Everyone else in the split (the payer too, when someone else paid).
  const others = payer === "them" && paidBy !== null ? [...new Set([paidBy, ...withIds])] : withIds;
  const equal = splitEvenly(total, others.length + 1); // [your share, ...theirs]

  let yourShare: number | undefined;
  let shares: { person_id: number; cents: number }[] = [];
  if (mode === "equal") {
    yourShare = total ? equal[0] : 0;
    shares = payer === "me" ? withIds.map((id, i) => ({ person_id: id, cents: equal[i + 1] })) : [];
  } else if (payer === "me") {
    shares = withIds.map((id) => ({ person_id: id, cents: parseDollars(custom[id] ?? "") ?? 0 }));
    yourShare = total - shares.reduce((s, x) => s + x.cents, 0);
  } else {
    yourShare = parseDollars(yourShareText) ?? 0;
  }

  const problem =
    !description.trim() ? "Add a description." :
    !total ? "Enter the amount." :
    payer === "me" && withIds.length === 0 ? "Choose who you split it with." :
    payer === "them" && paidBy === null ? "Choose who paid." :
    yourShare === undefined || yourShare < 0 ? "The shares add up to more than the total." :
    yourShare > total ? "Your share can't be more than the total." : null;

  const pickGroup = (id: number | null) => {
    setGroupId(id);
    const group = groups.find((g) => g.id === id);
    if (group) setWithIds(group.members.map((m) => m.id).filter((m) => m !== paidBy));
  };

  const toggle = (id: number) => setWithIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));

  const save = async () => {
    if (problem || yourShare === undefined) return;
    setSaving(true);
    setError(null);
    const expense: NewSharedExpense = {
      date, description: description.trim(), category, total_cents: total, your_share_cents: yourShare,
      paid_by: payer === "me" ? null : paidBy, shares, group_id: groupId,
    };
    try {
      await db.addShared(expense);
      setDescription("");
      setAmount("");
      setCustom({});
      setYourShareText("");
      onSaved();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setSaving(false);
    }
  };

  const toggleButton = (active: boolean) =>
    `rounded-lg border px-4 py-2.5 text-sm font-medium transition-colors ${
      active ? "border-accent bg-accent text-accent-ink" : "border-line bg-surface text-ink hover:bg-surface-muted"
    }`;

  if (people.length === 0) {
    return (
      <Card className="p-6 mb-6">
        <CardTitle>Add shared expense</CardTitle>
        <p className="text-sm text-muted">
          First add the people you split with on{" "}
          <button onClick={onPeople} className="font-medium text-ink underline underline-offset-4">People</button>, or import from Splitwise.
        </p>
      </Card>
    );
  }

  return (
    <Card className="p-6 mb-6">
      <CardTitle>Add shared expense</CardTitle>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <label className={label}>Description</label>
          <input value={description} onChange={(e) => setDescription(e.target.value)} className={`w-full ${field}`} placeholder="Dinner at Olive Garden" />
        </div>
        <div>
          <label className={label}>Amount</label>
          <input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" placeholder="0.00"
            className={`w-full tabular-nums ${field} ${parseDollars(amount) === undefined ? "border-red-500" : ""}`} />
        </div>
        <div>
          <label className={label}>Category</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)} className={`w-full ${field}`}>
            {reference?.categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className={label}>Date</label>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={`w-full ${field}`} />
        </div>
      </div>

      <div className="mt-5">
        <label className={label}>Who paid?</label>
        <div className="grid grid-cols-2 gap-3 md:max-w-md">
          <button type="button" className={toggleButton(payer === "me")} onClick={() => setPayer("me")}>I paid</button>
          <button type="button" className={toggleButton(payer === "them")} onClick={() => setPayer("them")}>Someone else paid</button>
        </div>
        {payer === "them" && (
          <select value={paidBy ?? ""} onChange={(e) => setPaidBy(e.target.value ? Number(e.target.value) : null)} className={`mt-3 w-full md:max-w-md ${field}`}>
            <option value="">Who paid the bill?</option>
            {people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        )}
      </div>

      <div className="mt-5 rounded-xl border border-line p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <span className="text-sm font-medium text-ink-soft">{payer === "me" ? "Split with" : "Also in the split"}</span>
          {groups.length > 0 && (
            <select value={groupId ?? ""} onChange={(e) => pickGroup(e.target.value ? Number(e.target.value) : null)} className={field}>
              <option value="">No group</option>
              {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
          )}
        </div>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          {people.filter((p) => !(payer === "them" && p.id === paidBy)).map((p) => (
            <label key={p.id} className="flex cursor-pointer items-center justify-between rounded-lg border border-line px-4 py-3 text-sm text-ink hover:bg-surface-muted">
              {p.name}
              <input type="checkbox" checked={withIds.includes(p.id)} onChange={() => toggle(p.id)} />
            </label>
          ))}
        </div>
      </div>

      <div className="mt-5">
        <label className={label}>How is it split?</label>
        <div className="grid grid-cols-2 gap-3 md:max-w-md">
          <button type="button" className={toggleButton(mode === "equal")} onClick={() => setMode("equal")}>Equally</button>
          <button type="button" className={toggleButton(mode === "custom")} onClick={() => setMode("custom")}>Custom amounts</button>
        </div>
        {mode === "custom" && payer === "me" && withIds.length > 0 && (
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
            {withIds.map((id) => (
              <div key={id}>
                <label className={label}>{people.find((p) => p.id === id)?.name} owes</label>
                <input value={custom[id] ?? ""} onChange={(e) => setCustom((c) => ({ ...c, [id]: e.target.value }))}
                  inputMode="decimal" placeholder="0.00" className={`w-full tabular-nums ${field}`} />
              </div>
            ))}
          </div>
        )}
        {mode === "custom" && payer === "them" && (
          <div className="mt-3 md:max-w-xs">
            <label className={label}>Your share</label>
            <input value={yourShareText} onChange={(e) => setYourShareText(e.target.value)} inputMode="decimal" placeholder="0.00"
              className={`w-full tabular-nums ${field}`} />
          </div>
        )}
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-4">
        <button onClick={save} disabled={saving || problem !== null} className={buttonPrimary}>
          {saving ? "Saving…" : "Save shared expense"}
        </button>
        {total > 0 && yourShare !== undefined && yourShare >= 0 && yourShare <= total && (
          <span className="text-sm text-muted">
            Your share <span className="font-semibold text-ink tabular-nums">{formatMoney(yourShare)}</span>
            {payer === "me"
              ? ` · others owe you ${formatMoney(total - yourShare)}`
              : paidBy !== null && ` · you owe ${people.find((p) => p.id === paidBy)?.name} ${formatMoney(yourShare)}`}
          </span>
        )}
        {problem && (description || amount) && <span className="text-sm text-muted">{problem}</span>}
        {error && <span className="text-sm text-red-600 dark:text-red-400">{error}</span>}
      </div>
      {payer === "me" && (
        <p className="mt-3 text-xs text-faint">
          Paid by card? Link it to the card charge on Reconcile so the charge counts as your share instead of the full {total ? formatMoney(total) : "amount"}.
        </p>
      )}
    </Card>
  );
}

