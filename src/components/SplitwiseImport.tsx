import { useRef, useState } from "react";
import { FileText, Upload } from "lucide-react";
import { db, SplitwisePreview, SplitwiseResult } from "../lib/db";
import { Card, CardTitle, PageHeader, buttonGhost, buttonPrimary, field } from "./ui";

const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** Upload a Splitwise export, say which member you are, then import. */
export function SplitwiseImport({ onDone, onReconcile }: { onDone: () => void; onReconcile: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<SplitwisePreview | null>(null);
  const [you, setYou] = useState("");
  const [groupName, setGroupName] = useState("");
  const [result, setResult] = useState<SplitwiseResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const choose = async (f: File | null) => {
    setFile(f);
    setPreview(null);
    setResult(null);
    setError(null);
    setYou("");
    if (!f) return;
    // Splitwise names exports after the group, e.g. "apartment_2026-11-10_export.csv".
    setGroupName(f.name.replace(/\.csv$/i, "").replace(/_?\d{4}-\d{2}-\d{2}.*$/, "").replace(/[_-]+/g, " ").trim());
    try {
      setPreview(await db.previewSplitwise(f));
    } catch (e) {
      setError(errorText(e));
    }
  };

  const run = async () => {
    if (!file || !you) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await db.importSplitwise(file, you, groupName));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Import from Splitwise"
        subtitle="On splitwise.com, open a group or friend, choose Export as spreadsheet, then upload the CSV here."
        actions={<button className={buttonGhost} onClick={onDone}>Back to shared</button>}
      />

      <Card className="p-6 max-w-3xl">
        <CardTitle>Splitwise CSV</CardTitle>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="flex w-full flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-field px-4 py-8 text-sm hover:border-muted hover:bg-surface-muted"
        >
          {file ? <FileText size={26} className="text-ink" /> : <Upload size={26} className="text-faint" />}
          <span className="text-ink-soft">{file ? file.name : "Choose a Splitwise export"}</span>
        </button>
        <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden"
          onChange={(e) => { choose(e.target.files?.[0] ?? null); e.target.value = ""; }} />

        {preview && !result && (
          <div className="mt-5 space-y-4">
            <p className="text-sm text-muted">
              {preview.rows} rows{preview.payments ? `, ${preview.payments} of them payments` : ""}
              {preview.first_date && ` · ${preview.first_date} to ${preview.last_date}`}
            </p>
            <div>
              <p className="mb-2 text-sm font-medium text-ink-soft">Which one is you?</p>
              <div className="flex flex-wrap gap-2">
                {preview.members.map((m) => (
                  <button key={m} type="button" onClick={() => setYou(m)}
                    className={`rounded-lg border px-4 py-2 text-sm font-medium ${you === m ? "border-accent bg-accent text-accent-ink" : "border-line bg-surface text-ink hover:bg-surface-muted"}`}>
                    {m}
                  </button>
                ))}
              </div>
            </div>
            <div className="md:max-w-sm">
              <label className="mb-2 block text-sm font-medium text-ink-soft">Group (optional)</label>
              <input value={groupName} onChange={(e) => setGroupName(e.target.value)} className={`w-full ${field}`} placeholder="Apartment" />
            </div>
            <button onClick={run} disabled={!you || busy} className={buttonPrimary}>
              {busy ? "Importing…" : "Confirm import"}
            </button>
            <p className="text-xs text-faint">Importing the same file again later only adds what's new.</p>
          </div>
        )}

        {error && <p className="mt-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

        {result && (
          <div className="mt-5 space-y-3 text-sm">
            <p className="font-medium text-ink">
              Imported {result.imported} shared expense{result.imported === 1 ? "" : "s"}
              {result.settlements ? ` and ${result.settlements} settlement${result.settlements === 1 ? "" : "s"}` : ""}.
            </p>
            <ul className="space-y-1 text-muted">
              {result.already_imported > 0 && <li>{result.already_imported} were already imported.</li>}
              {result.not_involving_you > 0 && <li>{result.not_involving_you} didn't involve you.</li>}
            </ul>
            {result.skipped.length > 0 && (
              <details className="text-ink-soft">
                <summary className="cursor-pointer">{result.skipped.length} row(s) skipped</summary>
                <ul className="mt-1 space-y-1 font-mono text-xs">
                  {result.skipped.map((r, i) => <li key={i}>{r.line} <span className="text-muted">— {r.reason}</span></li>)}
                </ul>
              </details>
            )}
            <p className="text-muted">
              Expenses you paid by card count once they're linked to the card charge.{" "}
              <button onClick={onReconcile} className="font-medium text-ink underline underline-offset-4">Go to Reconcile</button>
            </p>
            <button onClick={onDone} className={buttonPrimary}>Done</button>
          </div>
        )}
      </Card>
    </div>
  );
}
