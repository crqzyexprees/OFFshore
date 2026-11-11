import { FormEvent, useEffect, useState } from "react";
import { Trash2, UsersRound, X } from "lucide-react";
import { db, Group, Person } from "../lib/db";
import { Card, CardTitle, EmptyState, PageHeader, buttonGhost, buttonPrimary, field } from "../components/ui";

const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e));

export function Groups({ onPeople }: { onPeople: () => void }) {
  const [groups, setGroups] = useState<Group[] | null>(null);
  const [people, setPeople] = useState<Person[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    Promise.all([db.getGroups(), db.getPeople()]).then(([g, p]) => {
      setGroups(g);
      setPeople(p);
    }, (e) => setError(errorText(e)));
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

  const create = async (e: FormEvent) => {
    e.preventDefault();
    if (name.trim() && (await act(() => db.addGroup(name.trim())))) setName("");
  };

  return (
    <div>
      <PageHeader title="Groups" subtitle="Housemates, trips, teams: people you often split with together." />

      <Card className="p-6 mb-6">
        <CardTitle>Create group</CardTitle>
        <form onSubmit={create} className="flex flex-wrap gap-3">
          <input className={`flex-1 min-w-48 ${field}`} placeholder="Group name" value={name} onChange={(e) => setName(e.target.value)} aria-label="Group name" />
          <button className={buttonPrimary} disabled={!name.trim()}>Create</button>
        </form>
        {error && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
      </Card>

      {groups && groups.length === 0 ? (
        <Card>
          <EmptyState icon={<UsersRound size={36} />} title="No groups yet" hint="Create one above, or import a Splitwise group export." />
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {(groups ?? []).map((g) => (
            <GroupCard key={g.id} group={g} people={people} onPeople={onPeople}
              onAdd={(pid) => act(() => db.addMember(g.id, pid))}
              onRemove={(pid) => act(() => db.removeMember(g.id, pid))}
              onDelete={() => confirm(`Delete the group ${g.name}? Its expenses are kept.`) && act(() => db.deleteGroup(g.id))} />
          ))}
        </div>
      )}
    </div>
  );
}

function GroupCard({ group, people, onPeople, onAdd, onRemove, onDelete }: {
  group: Group;
  people: Person[];
  onPeople: () => void;
  onAdd: (personId: number) => void;
  onRemove: (personId: number) => void;
  onDelete: () => void;
}) {
  const [choice, setChoice] = useState("");
  const members = new Set(group.members.map((m) => m.id));
  const candidates = people.filter((p) => !members.has(p.id));
  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="font-semibold text-ink">{group.name}</p>
        <button className="rounded-md p-1 text-faint hover:bg-surface-muted hover:text-ink" onClick={onDelete} aria-label={`Delete ${group.name}`} title="Delete group">
          <Trash2 size={16} />
        </button>
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        {group.members.length === 0 && <p className="text-sm text-muted">No members yet.</p>}
        {group.members.map((m) => (
          <span key={m.id} className="inline-flex items-center gap-1 rounded-full bg-surface-muted py-1 pl-3 pr-1.5 text-sm text-ink">
            {m.name}
            <button className="rounded-full p-0.5 text-faint hover:text-ink" onClick={() => onRemove(m.id)} aria-label={`Remove ${m.name}`}>
              <X size={14} />
            </button>
          </span>
        ))}
      </div>
      {candidates.length > 0 ? (
        <div className="flex gap-2">
          <select className={`flex-1 ${field}`} value={choice} onChange={(e) => setChoice(e.target.value)} aria-label="Person to add">
            <option value="">Add a member…</option>
            {candidates.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <button className={buttonGhost} disabled={!choice} onClick={() => { onAdd(Number(choice)); setChoice(""); }}>Add</button>
        </div>
      ) : (
        <p className="text-sm text-muted">
          Everyone's in. <button onClick={onPeople} className="font-medium text-ink underline underline-offset-4">Add a person</button>
        </p>
      )}
    </Card>
  );
}
