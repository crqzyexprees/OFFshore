import { useEffect, useState } from "react";
import { Pencil, Trash2, Users } from "lucide-react";
import { db, Group, NewSharedExpense, Person, Settlement, SharedExpense, Transaction } from "../lib/db";
import { categoryColor } from "../lib/categories";
import { formatMoney, useReference } from "../lib/reference";
import { dollars, parseDollars, splitEvenly, today } from "../lib/money";
import { SplitwiseImport } from "../components/SplitwiseImport";
import { Card, CardTitle, EmptyState, PageHeader, buttonGhost, buttonPrimary, field } from "../components/ui";

const label = "mb-2 block text-sm font-medium text-ink-soft";
const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e));

export function Shared({ onReconcile, onPeople, startImport = false, onImportClosed, fromCharge = null, onChargeUsed }: {
  onReconcile: () => void;
  onPeople: () => void;
  startImport?: boolean;
  onImportClosed?: () => void;
  /** A card charge to split ("Split" on Personal): the form starts from it, linked to it. */
  fromCharge?: Transaction | null;
  onChargeUsed?: () => void;
}) {
  const [people, setPeople] = useState<Person[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [expenses, setExpenses] = useState<SharedExpense[] | null>(null);
  const [settlements, setSettlements] = useState<Settlement[]>([]);
  const [importing, setImporting] = useState(startImport);
  const [editing, setEditing] = useState<SharedExpense | null>(null);
  const [charge, setCharge] = useState<Transaction | null>(fromCharge);
  const [paymentFor, setPaymentFor] = useState<{ personId: number; direction: Settlement["direction"] } | null>(null);
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

  /** Runs a change, reloads, and says whether it worked. */
  const act = async (action: () => Promise<unknown>) => {
    setError(null);
    try {
      await action();
      await load();
      return true;
    } catch (e) {
      setError(errorText(e));
      return false;
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

      <ExpenseForm
        key={editing ? `edit-${editing.id}` : charge ? `charge-${charge.id}` : "new"}
        people={people}
        groups={groups}
        onPeople={onPeople}
        editing={editing}
        fromCharge={charge}
        onDone={() => {
          setEditing(null);
          setCharge(null);
          onChargeUsed?.();
          load();
        }}
      />

      <Balances
        people={people}
        onSettle={(id) => act(() => db.settleUp(id, today()))}
        onPartPayment={(personId, direction) => {
          setPaymentFor({ personId, direction });
          document.getElementById("record-payment")?.scrollIntoView({ behavior: "smooth", block: "center" });
        }}
      />

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
              <ExpenseRow key={e.id} expense={e} onReconcile={onReconcile}
                onEdit={() => {
                  setCharge(null);
                  setEditing(e);
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
                onDelete={() => act(() => db.deleteShared(e.id))} />
            ))}
          </ul>
        )}
      </Card>

      {people.length > 0 && (
        <Card className="p-6">
          <CardTitle>Settlements</CardTitle>
          <PaymentForm
            key={paymentFor ? `${paymentFor.personId}-${paymentFor.direction}` : "none"}
            people={people}
            initial={paymentFor}
            onSave={async (payment) => {
              const saved = await act(() => db.addSettlement(payment));
              if (saved) setPaymentFor(null);
              return saved;
            }}
          />
          {settlements.length === 0 && <p className="text-sm text-muted">No payments recorded yet.</p>}
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

function ExpenseRow({ expense: e, onReconcile, onEdit, onDelete }: {
  expense: SharedExpense;
  onReconcile: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
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
          <span className="flex items-center">
            <button onClick={onEdit} aria-label={`Edit ${e.description}`} title="Edit"
              className="rounded-md p-1.5 text-faint hover:bg-surface-muted hover:text-ink">
              <Pencil size={15} />
            </button>
            <button onClick={() => setConfirming(true)} aria-label={`Delete ${e.description}`} title="Delete"
              className="rounded-md p-1.5 text-faint hover:bg-surface-muted hover:text-red-600 dark:hover:text-red-400">
              <Trash2 size={16} />
            </button>
          </span>
        )}
      </div>
      {status && <div className="mt-2 pl-27">{status}</div>}
    </li>
  );
}

function Balances({ people, onSettle, onPartPayment }: {
  people: Person[];
  onSettle: (id: number) => void;
  onPartPayment: (personId: number, direction: Settlement["direction"]) => void;
}) {
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
                <div className="mt-3 flex flex-wrap gap-2">
                  <button className={buttonPrimary} onClick={() => onSettle(p.id)}>Mark settled</button>
                  <button className={buttonGhost}
                    onClick={() => onPartPayment(p.id, p.balance_cents > 0 ? "from_them" : "to_them")}>
                    Record part payment
                  </button>
                </div>
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

type Draft = {
  description: string;
  amount: string;
  date: string;
  category: string;
  groupId: number | null;
  payer: Payer;
  paidBy: number | null;
  withIds: number[];
  mode: SplitMode;
  custom: Record<number, string>;
  yourShareText: string;
};

const BLANK: Draft = {
  description: "", amount: "", date: "", category: "Other", groupId: null, payer: "me", paidBy: null,
  withIds: [], mode: "equal", custom: {}, yourShareText: "",
};

/** The form's starting point: blank, an expense being edited, or a card charge to split. */
function startFrom(editing: SharedExpense | null, charge: Transaction | null): Draft {
  if (editing) {
    const e = editing;
    const equal = splitEvenly(e.total_cents, e.shares.length + 1);
    const isEqual = e.paid_by === null && e.your_share_cents === equal[0] && e.shares.every((x, i) => x.cents === equal[i + 1]);
    return {
      description: e.description, amount: dollars(e.total_cents), date: e.date, category: e.category,
      groupId: e.group_id, payer: e.paid_by === null ? "me" : "them", paidBy: e.paid_by,
      withIds: e.shares.map((x) => x.person_id),
      mode: isEqual ? "equal" : "custom",
      custom: Object.fromEntries(e.shares.map((x) => [x.person_id, dollars(x.cents)])),
      yourShareText: dollars(e.your_share_cents),
    };
  }
  if (charge) {
    return { ...BLANK, description: charge.description, amount: dollars(charge.amount_cents), date: charge.date,
             category: charge.category ?? "Other" };
  }
  return { ...BLANK, date: today() };
}

function ExpenseForm({ people, groups, onPeople, editing, fromCharge, onDone }: {
  people: Person[];
  groups: Group[];
  onPeople: () => void;
  /** Editing this expense instead of adding one. */
  editing: SharedExpense | null;
  /** Adding an expense made from this card charge, linked to it. */
  fromCharge: Transaction | null;
  /** Saved or cancelled. */
  onDone: () => void;
}) {
  const reference = useReference();
  const [draft, setDraft] = useState<Draft>(() => startFrom(editing, fromCharge));
  const set = (part: Partial<Draft>) => setDraft((d) => ({ ...d, ...part }));
  const { description, amount, date, category, groupId, payer, paidBy, withIds, mode, custom, yourShareText } = draft;
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The card charge this expense is (or will be) linked to: only possible when you paid.
  const charge = fromCharge
    ? { description: fromCharge.description, amount_cents: fromCharge.amount_cents, id: fromCharge.id }
    : editing?.transaction ?? null;

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
    yourShare = total - shares.reduce((sum, x) => sum + x.cents, 0);
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
    const group = groups.find((g) => g.id === id);
    set({ groupId: id, ...(group && { withIds: group.members.map((m) => m.id).filter((m) => m !== paidBy) }) });
  };

  const toggle = (id: number) => set({ withIds: withIds.includes(id) ? withIds.filter((x) => x !== id) : [...withIds, id] });

  const save = async () => {
    if (problem || yourShare === undefined) return;
    setSaving(true);
    setError(null);
    const youPaid = payer === "me";
    const expense: NewSharedExpense = {
      date, description: description.trim(), category, total_cents: total, your_share_cents: yourShare,
      paid_by: youPaid ? null : paidBy, shares, group_id: groupId,
      // Only an expense you paid keeps its card charge, or stays "paid outside your accounts".
      transaction_id: youPaid ? charge?.id ?? null : null,
      standalone: youPaid && !charge && (editing?.standalone ?? false),
    };
    try {
      if (editing) await db.updateShared(editing.id, expense);
      else await db.addShared(expense);
      if (!editing && !fromCharge) setDraft({ ...startFrom(null, null), date, category, groupId, payer, paidBy, withIds });
      onDone();
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
      <CardTitle actions={(editing || fromCharge) && <button className={buttonGhost} onClick={onDone}>Cancel</button>}>
        {editing ? "Edit shared expense" : fromCharge ? "Split a card charge" : "Add shared expense"}
      </CardTitle>
      {charge && (
        <p className="mb-4 rounded-lg bg-surface-muted px-4 py-2.5 text-sm text-ink-soft">
          {payer === "me"
            ? <>Linked to the card charge <span className="font-medium text-ink">{charge.description}</span> ({formatMoney(charge.amount_cents)}): it counts as your share, not the full amount.</>
            : <>Someone else paid, so this won't stay linked to the card charge {charge.description}.</>}
        </p>
      )}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <label className={label}>Description</label>
          <input value={description} onChange={(e) => set({ description: e.target.value })} className={`w-full ${field}`} placeholder="Dinner at Olive Garden" />
        </div>
        <div>
          <label className={label}>Amount</label>
          <input value={amount} onChange={(e) => set({ amount: e.target.value })} inputMode="decimal" placeholder="0.00"
            className={`w-full tabular-nums ${field} ${parseDollars(amount) === undefined ? "border-red-500" : ""}`} />
        </div>
        <div>
          <label className={label}>Category</label>
          <select value={category} onChange={(e) => set({ category: e.target.value })} className={`w-full ${field}`}>
            {reference?.categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className={label}>Date</label>
          <input type="date" value={date} onChange={(e) => set({ date: e.target.value })} className={`w-full ${field}`} />
        </div>
      </div>

      <div className="mt-5">
        <label className={label}>Who paid?</label>
        <div className="grid grid-cols-2 gap-3 md:max-w-md">
          <button type="button" className={toggleButton(payer === "me")} onClick={() => set({ payer: "me" })}>I paid</button>
          <button type="button" className={toggleButton(payer === "them")} onClick={() => set({ payer: "them" })}>Someone else paid</button>
        </div>
        {payer === "them" && (
          <select value={paidBy ?? ""} onChange={(e) => set({ paidBy: e.target.value ? Number(e.target.value) : null })} className={`mt-3 w-full md:max-w-md ${field}`}>
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
          <button type="button" className={toggleButton(mode === "equal")} onClick={() => set({ mode: "equal" })}>Equally</button>
          <button type="button" className={toggleButton(mode === "custom")} onClick={() => set({ mode: "custom" })}>Custom amounts</button>
        </div>
        {mode === "custom" && payer === "me" && withIds.length > 0 && (
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
            {withIds.map((id) => (
              <div key={id}>
                <label className={label}>{people.find((p) => p.id === id)?.name} owes</label>
                <input value={custom[id] ?? ""} onChange={(e) => set({ custom: { ...custom, [id]: e.target.value } })}
                  inputMode="decimal" placeholder="0.00" className={`w-full tabular-nums ${field}`} />
              </div>
            ))}
          </div>
        )}
        {mode === "custom" && payer === "them" && (
          <div className="mt-3 md:max-w-xs">
            <label className={label}>Your share</label>
            <input value={yourShareText} onChange={(e) => set({ yourShareText: e.target.value })} inputMode="decimal" placeholder="0.00"
              className={`w-full tabular-nums ${field}`} />
          </div>
        )}
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-4">
        <button onClick={save} disabled={saving || problem !== null} className={buttonPrimary}>
          {saving ? "Saving…" : editing ? "Save changes" : "Save shared expense"}
        </button>
        {!problem && yourShare !== undefined && (
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
      {payer === "me" && !charge && (
        <p className="mt-3 text-xs text-faint">
          Paid by card? Link it to the card charge on Reconcile so the charge counts as your share instead of the full {total ? formatMoney(total) : "amount"}.
        </p>
      )}
    </Card>
  );
}

function PaymentForm({ people, initial, onSave }: {
  people: Person[];
  initial: { personId: number; direction: Settlement["direction"] } | null;
  onSave: (payment: Omit<Settlement, "id" | "name">) => Promise<boolean>;
}) {
  const [personId, setPersonId] = useState<number | null>(initial?.personId ?? null);
  const [direction, setDirection] = useState<Settlement["direction"]>(initial?.direction ?? "from_them");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(today);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const cents = parseDollars(amount);
  const person = people.find((p) => p.id === personId);

  const save = async () => {
    if (personId === null || !cents) return;
    setSaving(true);
    const saved = await onSave({ person_id: personId, direction, cents, date, note: note.trim() || null });
    setSaving(false);
    if (saved) {
      setAmount("");
      setNote("");
    }
  };

  return (
    <div id="record-payment" className="mb-5 rounded-xl border border-line p-4">
      <p className="mb-3 text-sm font-medium text-ink-soft">Record a payment</p>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_1fr_8rem_10rem]">
        <select value={personId ?? ""} onChange={(e) => setPersonId(e.target.value ? Number(e.target.value) : null)}
          className={field} aria-label="Person" autoFocus={initial !== null}>
          <option value="">Who?</option>
          {people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select value={direction} onChange={(e) => setDirection(e.target.value as Settlement["direction"])}
          className={field} aria-label="Who paid">
          <option value="from_them">{person ? `${person.name} paid me` : "They paid me"}</option>
          <option value="to_them">{person ? `I paid ${person.name}` : "I paid them"}</option>
        </select>
        <input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" placeholder="0.00"
          aria-label="Amount" className={`tabular-nums ${field} ${cents === undefined ? "border-red-500" : ""}`} />
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-label="Date" className={field} />
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note (optional), e.g. Venmo"
          aria-label="Note" className={`min-w-48 flex-1 ${field}`} />
        <button className={buttonPrimary} disabled={saving || personId === null || !cents} onClick={save}>
          {saving ? "Saving…" : "Record payment"}
        </button>
      </div>
      {person && person.balance_cents !== 0 && (
        <p className="mt-2 text-xs text-faint">
          {person.balance_cents > 0
            ? `${person.name} owes you ${formatMoney(person.balance_cents)}`
            : `You owe ${person.name} ${formatMoney(-person.balance_cents)}`}. Payments change the balance, never your spending.
        </p>
      )}
    </div>
  );
}
