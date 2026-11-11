import { useRef, useState } from "react";
import { FileText, Upload } from "lucide-react";
import { db, Account, ApiError, ImportProblem, ImportResult } from "../lib/db";
import { bankName, formatMoney, useReference } from "../lib/reference";

interface UploaderProps {
  accounts: Account[];
  onImported: () => void;
}

/** Why the last attempt failed: an ImportProblem, or any other error's message. */
type Problem = ImportProblem | { problem?: undefined; message: string };

/** Upload a Statement or Export, asking for its Account or period when the file doesn't say. */
export function StatementUploader({ accounts, onImported }: UploaderProps) {
  const reference = useReference();
  const [file, setFile] = useState<File | null>(null);
  const [accountId, setAccountId] = useState<number | null>(null);
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [result, setResult] = useState<ImportResult | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [loading, setLoading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const needsPeriod = problem?.problem === "needs_period";
  const needsAccount = problem?.problem === "needs_account";

  const handleImport = async () => {
    if (!file) return;
    setLoading(true);
    setProblem(null);
    setResult(null);
    try {
      setResult(
        await db.importStatement(file, {
          accountId: accountId ?? undefined,
          period: periodStart && periodEnd ? { start: periodStart, end: periodEnd } : undefined,
        })
      );
      onImported();
    } catch (e) {
      if (e instanceof ApiError && e.problem) {
        setProblem(e.problem);
        // The backend matched the Account; keep it so the next attempt uses it.
        if (e.problem.problem === "needs_period") setAccountId(e.problem.account_id);
      } else {
        setProblem({ message: e instanceof Error ? e.message : String(e) });
      }
    } finally {
      setLoading(false);
    }
  };

  const pickFile = (f: File | null) => {
    setFile(f);
    setProblem(null);
    setResult(null);
    setPeriodStart("");
    setPeriodEnd("");
  };

  const accountName = (id: number) => accounts.find((a) => a.id === id)?.name ?? `#${id}`;

  return (
    <div>
      <p className="text-sm text-muted mb-4">
        PDF, CSV, OFX or QFX. Statements are read and categorized on this device. Uploading the same
        billing period again replaces it and keeps your edits.
      </p>

      {accounts.length === 0 ? (
        <p className="text-sm text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 rounded-lg p-3">
          Add an account first (on the Accounts page), then upload its statements here.
        </p>
      ) : (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-ink-soft mb-1">File</label>
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                const dropped = e.dataTransfer.files[0];
                if (dropped) pickFile(dropped);
              }}
              className={`w-full flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-10 text-sm transition-colors ${
                dragging
                  ? "border-ink bg-accent-soft"
                  : "border-field hover:border-muted hover:bg-surface-muted"
              }`}
            >
              {file ? (
                <>
                  <FileText size={28} className="text-ink" />
                  <span className="font-medium text-ink break-all">{file.name}</span>
                  <span className="text-xs text-muted">{(file.size / 1024).toFixed(0)} KB · click to choose another</span>
                </>
              ) : (
                <>
                  <Upload size={28} className="text-faint" />
                  <span className="text-ink-soft">
                    Drop a statement here or <span className="text-ink font-medium underline underline-offset-4">browse</span>
                  </span>
                </>
              )}
            </button>
            <input
              ref={inputRef}
              type="file"
              accept="application/pdf,.pdf,.csv,.ofx,.qfx"
              onChange={(e) => {
                pickFile(e.target.files?.[0] ?? null);
                e.target.value = "";
              }}
              className="hidden"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-ink-soft mb-1">Account</label>
            <select
              className={`w-full border rounded-lg px-3 py-2 text-sm ${
                needsAccount ? "border-amber-500 dark:border-amber-600 ring-2 ring-amber-200 dark:ring-amber-900" : "border-line"
              }`}
              value={accountId ?? ""}
              onChange={(e) => setAccountId(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">Detect from the statement</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                  {a.last_four ? ` •••• ${a.last_four}` : ""}
                </option>
              ))}
            </select>
          </div>

          {needsPeriod && (
            <div className="rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 p-3 space-y-2">
              <p className="text-sm text-amber-900 dark:text-amber-200">Enter the billing period printed on the statement.</p>
              <div className="flex gap-2 items-center text-sm">
                <input
                  type="date"
                  value={periodStart}
                  onChange={(e) => setPeriodStart(e.target.value)}
                  className="border border-line rounded-lg px-2 py-1"
                />
                <span className="text-muted">to</span>
                <input
                  type="date"
                  value={periodEnd}
                  onChange={(e) => setPeriodEnd(e.target.value)}
                  className="border border-line rounded-lg px-2 py-1"
                />
              </div>
            </div>
          )}

          <button
            onClick={handleImport}
            disabled={!file || loading || (needsPeriod && !(periodStart && periodEnd))}
            className="w-full bg-accent hover:bg-accent-hover text-accent-ink py-2.5 rounded-lg text-sm font-medium"
          >
            {loading ? (
              <span className="inline-flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-current/40 border-t-current rounded-full animate-spin" />
                Reading & classifying…
              </span>
            ) : (
              "Upload statement"
            )}
          </button>
        </div>
      )}

      {problem && !needsPeriod && (
        <div className="mt-4 p-4 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-lg text-sm space-y-2">
          <p className="text-red-700 dark:text-red-300">{problem.message}</p>
          {problem.problem === "no_transactions" && problem.rejected.length > 0 && (
            <RejectedRows rows={problem.rejected} />
          )}
        </div>
      )}

      {result && (
        <div className="mt-4 p-4 bg-green-50 dark:bg-emerald-950/40 border border-green-200 dark:border-emerald-900 rounded-lg space-y-2 text-sm">
          <p className="font-medium text-green-800 dark:text-emerald-200">
            {result.replaced ? "Statement replaced" : "Statement imported"}
          </p>
          <p className="text-green-700 dark:text-emerald-300">
            {result.imported} transactions · {accountName(result.account_id)} ·{" "}
            {bankName(reference, result.bank)} · {result.period_start} to {result.period_end}
          </p>
          {result.unmatched_overrides.length > 0 && (
            <div className="text-amber-800 dark:text-amber-300">
              <p className="font-medium">
                {result.unmatched_overrides.length} edit(s) couldn't be matched to the new import:
              </p>
              <ul className="list-disc pl-5">
                {result.unmatched_overrides.map((o, i) => (
                  <li key={i}>
                    {o.date} {o.description} {formatMoney(o.amount_cents)} →{" "}
                    {[o.override_kind, o.override_category].filter(Boolean).join(", ")}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {result.rejected.length > 0 && <RejectedRows rows={result.rejected} />}
        </div>
      )}
    </div>
  );
}

function RejectedRows({ rows }: { rows: { line: string; reason: string }[] }) {
  return (
    <details className="text-ink-soft">
      <summary className="cursor-pointer">{rows.length} line(s) skipped</summary>
      <ul className="mt-1 space-y-1 font-mono text-xs">
        {rows.map((r, i) => (
          <li key={i}>
            {r.line} <span className="text-muted">— {r.reason}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}
