import { useEffect, useRef, useState } from "react";
import { db } from "../lib/db";
import { Card, CardTitle, buttonGhost, buttonPrimary, field } from "./ui";

type Status = { kind: "ok" | "error"; text: string } | null;

/** Save the whole database to a file, or replace it with one. */
export function Backups() {
  const [location, setLocation] = useState<{ directory: string; min_password: number } | null>(null);
  const [encrypt, setEncrypt] = useState(true);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<Status>(null);

  const [file, setFile] = useState<File | null>(null);
  const [restorePassword, setRestorePassword] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [restored, setRestored] = useState<Status>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    db.getBackupLocation().then(setLocation, (e) => setSaved({ kind: "error", text: String(e.message ?? e) }));
  }, []);

  const minPassword = location?.min_password ?? 8;
  const passwordProblem = !encrypt
    ? null
    : password.length < minPassword
      ? `At least ${minPassword} characters.`
      : password !== confirm
        ? "The passwords don't match."
        : null;
  const encryptedFile = file?.name.endsWith(".splitlens-backup") ?? false;

  const save = async () => {
    setSaving(true);
    setSaved(null);
    try {
      const result = await db.saveBackup(encrypt ? password : null);
      setSaved({ kind: "ok", text: `Saved to ${result.path}` });
      setPassword("");
      setConfirm("");
    } catch (e) {
      setSaved({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    } finally {
      setSaving(false);
    }
  };

  const restore = async () => {
    if (!file) return;
    setRestoring(true);
    setRestored(null);
    try {
      const result = await db.restoreBackup(file, restorePassword || null);
      setRestored({ kind: "ok", text: `Restored. Your data from before is saved at ${result.previous}` });
      setFile(null);
      setRestorePassword("");
    } catch (e) {
      setRestored({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    } finally {
      setRestoring(false);
      setConfirming(false);
    }
  };

  return (
    <Card className="p-6 space-y-5">
      <div>
        <CardTitle>Backups</CardTitle>
        <p className="text-sm text-muted -mt-2">
          A Backup is a copy of all your Accounts, Statements and corrections.
          {location && <> Saved in <span className="font-mono break-all">{location.directory}</span>.</>}
        </p>
      </div>

      <div className="space-y-3">
        <label className="flex items-center gap-2 text-sm text-ink cursor-pointer">
          <input type="checkbox" checked={encrypt} onChange={(e) => setEncrypt(e.target.checked)} />
          Encrypt with a password
        </label>
        {encrypt ? (
          <div className="space-y-2">
            <input type="password" placeholder="Password" value={password} autoComplete="new-password"
              onChange={(e) => setPassword(e.target.value)} className={`w-full ${field}`} />
            <input type="password" placeholder="Type it again" value={confirm} autoComplete="new-password"
              onChange={(e) => setConfirm(e.target.value)} className={`w-full ${field}`} />
            <p className="text-xs text-muted">
              The password isn't stored anywhere. If you forget it, the Backup can't be opened.
            </p>
          </div>
        ) : (
          <p className="text-xs text-amber-700 dark:text-amber-300">
            Without a password, anyone who gets the file can read your transactions.
          </p>
        )}
        <button onClick={save} disabled={saving || passwordProblem !== null} className={buttonPrimary}>
          {saving ? "Saving…" : "Save Backup"}
        </button>
        {encrypt && password && passwordProblem && <p className="text-xs text-muted">{passwordProblem}</p>}
        {saved && <StatusLine status={saved} />}
      </div>

      <div className="space-y-3 border-t border-line pt-4">
        <h3 className="text-sm font-medium text-ink">Restore</h3>
        <button type="button" onClick={() => inputRef.current?.click()} className={buttonGhost}>
          {file ? file.name : "Choose a Backup…"}
        </button>
        <input ref={inputRef} type="file" accept=".splitlens-backup,.db" className="hidden"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setConfirming(false);
            setRestored(null);
            e.target.value = "";
          }} />
        {file && encryptedFile && (
          <input type="password" placeholder="Backup password" value={restorePassword} autoComplete="off"
            onChange={(e) => setRestorePassword(e.target.value)} className={`w-full ${field}`} />
        )}
        {file && !confirming && (
          <button onClick={() => setConfirming(true)} disabled={encryptedFile && !restorePassword} className={buttonGhost}>
            Restore this Backup
          </button>
        )}
        {confirming && (
          <div className="rounded-lg border border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/40 p-3 space-y-2">
            <p className="text-sm text-amber-800 dark:text-amber-200">
              This replaces all your current data with the Backup. A copy of your current data is saved first.
            </p>
            <div className="flex gap-2">
              <button onClick={restore} disabled={restoring} className={buttonPrimary}>
                {restoring ? "Restoring…" : "Replace my data"}
              </button>
              <button onClick={() => setConfirming(false)} disabled={restoring} className={buttonGhost}>Cancel</button>
            </div>
          </div>
        )}
        {restored && <StatusLine status={restored} />}
      </div>
    </Card>
  );
}

function StatusLine({ status }: { status: NonNullable<Status> }) {
  const color = status.kind === "ok" ? "text-emerald-700 dark:text-emerald-400" : "text-red-600 dark:text-red-400";
  return <p className={`text-sm break-all ${color}`}>{status.text}</p>;
}
