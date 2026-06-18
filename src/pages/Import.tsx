import { useState } from "react";
import { db, ImportResult } from "../lib/db";

interface ImportProps {
  accounts: { id: number; name: string }[];
}

export function Import({ accounts }: ImportProps) {
  const [accountId, setAccountId] = useState<number | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleImport = async () => {
    if (!accountId) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await db.importPdf(accountId);
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-lg">
      <h1 className="text-2xl font-semibold text-slate-900 mb-2">
        Import Statement
      </h1>
      <p className="text-sm text-slate-500 mb-6">
        Select a card and import a PDF statement. Transactions are parsed locally
        and classified on-device.
      </p>

      {accounts.length === 0 ? (
        <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3">
          Add a card first before importing statements.
        </p>
      ) : (
        <>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Select Card
          </label>
          <select
            className="w-full border border-slate-300 rounded-lg px-3 py-2 mb-4 text-sm"
            value={accountId ?? ""}
            onChange={(e) => setAccountId(Number(e.target.value))}
          >
            <option value="">Choose a card...</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>

          <button
            onClick={handleImport}
            disabled={!accountId || loading}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white py-2.5 rounded-lg disabled:opacity-50 text-sm font-medium"
          >
            {loading ? "Parsing & Classifying..." : "Select PDF to Import"}
          </button>
        </>
      )}

      {result && (
        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
          <p className="font-medium text-green-800">Import complete</p>
          <p className="text-sm text-green-700">Bank detected: {result.bank}</p>
          <p className="text-sm text-green-700">
            Imported: {result.imported} transactions
          </p>
          {result.duplicates > 0 && (
            <p className="text-sm text-yellow-700">
              Duplicates skipped: {result.duplicates}
            </p>
          )}
          {result.failed > 0 && (
            <p className="text-sm text-red-600">
              Failed to parse: {result.failed}
            </p>
          )}
        </div>
      )}

      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}
    </div>
  );
}
