import { useEffect, useState } from "react";
import { FileText, Trash2, Upload, X } from "lucide-react";
import { Account, db, Statement } from "../lib/db";
import { monthLabel } from "../lib/month";
import { StatementUploader } from "../components/StatementUploader";
import { Card, CardTitle, EmptyState, PageHeader, buttonGhost, buttonPrimary } from "../components/ui";

const formatDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });

export function Statements({ accounts }: { accounts: Account[] }) {
  const [statements, setStatements] = useState<Statement[] | null>(null);
  const [uploading, setUploading] = useState(false);
  const [confirming, setConfirming] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => db.getStatements().then(setStatements, (e) => setError(String(e.message ?? e)));
  useEffect(() => {
    load();
  }, []);

  const remove = async (id: number) => {
    setConfirming(null);
    try {
      await db.deleteStatement(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  // Grouped by the month each billing period ends in, latest first.
  const byMonth = new Map<string, Statement[]>();
  for (const s of statements ?? []) {
    const month = s.period_end.slice(0, 7);
    byMonth.set(month, [...(byMonth.get(month) ?? []), s]);
  }
  const accountName = (id: number) => accounts.find((a) => a.id === id)?.name ?? "Deleted account";
  const showUploader = uploading || statements?.length === 0;

  return (
    <div>
      <PageHeader
        title="Statements"
        subtitle="Upload statements and review what was imported, by month."
        actions={
          !showUploader && (
            <button className={buttonPrimary} onClick={() => setUploading(true)}>
              <Upload size={15} /> Upload statement
            </button>
          )
        }
      />

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {showUploader && (
        <Card className="p-6 mb-6 max-w-2xl">
          <CardTitle
            actions={
              statements && statements.length > 0 && (
                <button className={buttonGhost} onClick={() => setUploading(false)} aria-label="Close">
                  <X size={15} />
                </button>
              )
            }
          >
            Upload statement
          </CardTitle>
          <StatementUploader accounts={accounts} onImported={load} />
        </Card>
      )}

      {statements && statements.length === 0 && !showUploader && (
        <Card>
          <EmptyState icon={<FileText size={36} />} title="No statements yet" />
        </Card>
      )}

      <div className="space-y-5">
        {[...byMonth].map(([month, list]) => (
          <Card key={month} className="p-5">
            <h2 className="text-lg font-semibold text-ink mb-3">{monthLabel(month)}</h2>
            <ul className="space-y-2">
              {list.map((s) => (
                <li key={s.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-line px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-ink">{s.file_name ?? "Statement"}</p>
                    <p className="text-sm text-muted">
                      {accountName(s.account_id)} · {formatDate(s.period_start)} – {formatDate(s.period_end)} ·{" "}
                      {s.transactions} transaction{s.transactions === 1 ? "" : "s"}
                    </p>
                  </div>
                  {confirming === s.id ? (
                    <span className="flex items-center gap-2 text-sm">
                      <span className="text-muted">Delete it and its transactions?</span>
                      <button onClick={() => remove(s.id)} className="rounded-md bg-red-600 px-2.5 py-1 font-medium text-white hover:bg-red-700">
                        Delete
                      </button>
                      <button onClick={() => setConfirming(null)} className="rounded-md px-2.5 py-1 text-ink-soft hover:bg-surface-muted">
                        Cancel
                      </button>
                    </span>
                  ) : (
                    <>
                      <span className="rounded-full bg-surface-muted px-2.5 py-0.5 text-xs font-medium text-ink-soft">Done</span>
                      <button
                        onClick={() => setConfirming(s.id)}
                        className="rounded-md p-1.5 text-faint hover:bg-surface-muted hover:text-red-600 dark:hover:text-red-400"
                        aria-label={`Delete ${s.file_name ?? "statement"}`}
                        title="Delete statement"
                      >
                        <Trash2 size={16} />
                      </button>
                    </>
                  )}
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
    </div>
  );
}
