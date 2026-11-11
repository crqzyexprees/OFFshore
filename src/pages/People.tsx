import { FormEvent, useEffect, useState } from "react";
import { Users, X } from "lucide-react";
import { db, Person } from "../lib/db";
import { formatMoney } from "../lib/reference";
import { Card, CardTitle, EmptyState, PageHeader, buttonPrimary, field } from "../components/ui";

const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e));

export function People() {
  const [people, setPeople] = useState<Person[] | null>(null);
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = () => db.getPeople().then(setPeople, (e) => setError(errorText(e)));
  useEffect(() => {
    load();
  }, []);

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

  const add = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    if (await act(() => db.addPerson(name.trim(), note.trim()))) {
      setName("");
      setNote("");
    }
  };

  return (
    <div>
      <PageHeader title="My people" subtitle="The people you split costs with." />

      <Card className="p-6 mb-6">
        <CardTitle>Add a person</CardTitle>
        <form onSubmit={add} className="flex flex-wrap items-end gap-3">
          <input className={`flex-1 min-w-48 ${field}`} placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} aria-label="Name" />
          <input className={`flex-[2] min-w-48 ${field}`} placeholder="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Note" />
          <button className={buttonPrimary} disabled={!name.trim()}>Add person</button>
        </form>
        {error && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
      </Card>

      {people && people.length === 0 ? (
        <Card>
          <EmptyState icon={<Users size={36} />} title="No people yet" hint="Add someone above, or import a Splitwise export to bring in its members." />
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {(people ?? []).map((p) => (
            <Card key={p.id} className="relative p-5">
              <button
                className="absolute right-3 top-3 rounded-md p-1 text-faint hover:bg-surface-muted hover:text-ink"
                aria-label={`Remove ${p.name}`}
                title="Remove"
                onClick={() => confirm(`Remove ${p.name}?`) && act(() => db.deletePerson(p.id))}
              >
                <X size={16} />
              </button>
              <p className="pr-6 font-semibold text-ink">{p.name}</p>
              {p.note && <p className="mt-1 text-sm text-muted">{p.note}</p>}
              <p className={`mt-3 text-sm font-medium tabular-nums ${
                p.balance_cents > 0 ? "text-emerald-700 dark:text-emerald-400" : p.balance_cents < 0 ? "text-red-600 dark:text-red-400" : "text-muted"
              }`}>
                {p.balance_cents > 0 ? `Owes you ${formatMoney(p.balance_cents)}` : p.balance_cents < 0 ? `You owe ${formatMoney(-p.balance_cents)}` : "Settled up"}
              </p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
