import { useEffect, useState } from "react";
import { Backups } from "../components/Backups";
import { inTauri, shell } from "../lib/backend";
import { Card, CardTitle, PageHeader, buttonPrimary } from "../components/ui";

export function Settings() {
  const [safeMode, setSafeMode] = useState<boolean | null>(null);
  const [changed, setChanged] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (inTauri) shell.getSafeMode().then(setSafeMode, (e) => setError(String(e)));
  }, []);

  const toggle = async () => {
    if (safeMode === null) return;
    try {
      await shell.setSafeMode(!safeMode);
      setSafeMode(!safeMode);
      setChanged(true);
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div className="max-w-3xl">
      <PageHeader title="Settings" subtitle="Backups and how the app runs on this computer." />

      <div className="space-y-6">
      <Backups />

      {inTauri && (
      <Card className="p-6 space-y-3">
        <CardTitle>Display</CardTitle>
        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={safeMode ?? false}
            disabled={safeMode === null}
            onChange={toggle}
            className="mt-1"
          />
          <span>
            <span className="block text-sm font-medium text-ink">
              Safe mode (software rendering)
            </span>
            <span className="block text-xs text-muted mt-0.5">
              Fixes a blank or glitchy window on some graphics drivers, mostly
              NVIDIA. Turned on automatically if the window fails to load.
            </span>
          </span>
        </label>

        {changed && (
          <button
            onClick={() => shell.restart()}
            className={buttonPrimary}
          >
            Restart to apply
          </button>
        )}
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      </Card>
      )}
      </div>
    </div>
  );
}
