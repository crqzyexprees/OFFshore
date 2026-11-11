import { useEffect, useState } from "react";
import { Backups } from "../components/Backups";
import { shell } from "../lib/backend";

export function Settings() {
  const [safeMode, setSafeMode] = useState<boolean | null>(null);
  const [changed, setChanged] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    shell.getSafeMode().then(setSafeMode, (e) => setError(String(e)));
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
    <div className="p-6 max-w-lg space-y-6">
      <h1 className="text-2xl font-semibold text-ink">Settings</h1>

      <div className="bg-surface rounded-xl shadow-sm border border-line p-4 space-y-3">
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
            className="bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1.5 rounded-lg text-sm font-medium"
          >
            Restart to apply
          </button>
        )}
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      </div>

      <Backups />
    </div>
  );
}
