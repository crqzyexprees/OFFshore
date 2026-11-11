import { useEffect, useState } from "react";
import { db, Account } from "./lib/db";
import { connectBackend, inTauri, reportUiReady, shell } from "./lib/backend";
import { Dashboard } from "./pages/Dashboard";
import { Transactions } from "./pages/Transactions";
import { Accounts } from "./pages/Accounts";
import { Import } from "./pages/Import";
import { Settings } from "./pages/Settings";
import { Budgets } from "./pages/Budgets";
import { ThemePreference, useThemePreference } from "./lib/theme";
import {
  ArrowLeftRight, LayoutDashboard, Target, LucideIcon, Monitor, Moon, Settings as SettingsIcon, Sun, Upload, Wallet,
} from "lucide-react";

type Page = "dashboard" | "budgets" | "transactions" | "accounts" | "import" | "settings";

const NAV: { id: Page; label: string; icon: LucideIcon }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "budgets", label: "Budgets", icon: Target },
  { id: "transactions", label: "Transactions", icon: ArrowLeftRight },
  { id: "accounts", label: "Accounts", icon: Wallet },
  { id: "import", label: "Import", icon: Upload },
  ...(inTauri ? [{ id: "settings" as const, label: "Settings", icon: SettingsIcon }] : []),
];

// The page lives in the URL hash, so a reload stays on it.
const pageFromHash = (): Page => {
  const id = window.location.hash.slice(1);
  return NAV.some((item) => item.id === id) ? (id as Page) : "dashboard";
};

function App() {
  const [page, setPageState] = useState<Page>(pageFromHash);
  const setPage = (next: Page) => {
    window.location.hash = next;
    setPageState(next);
  };
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [backend, setBackend] = useState<"connecting" | "ready" | Error>(
    "connecting"
  );

  const loadAccounts = () => db.getAccounts().then(setAccounts);

  const connect = () => {
    setBackend("connecting");
    connectBackend()
      .then(() => {
        setBackend("ready");
        loadAccounts();
      })
      .catch((e) => setBackend(e instanceof Error ? e : new Error(String(e))));
  };

  useEffect(() => {
    reportUiReady();
    connect();
  }, []);

  if (backend !== "ready") {
    return (
      <div className="min-h-screen bg-canvas flex items-center justify-center">
        {backend === "connecting" ? (
          <div className="flex flex-col items-center gap-3 text-muted">
            <div className="w-8 h-8 border-4 border-field border-t-indigo-600 rounded-full animate-spin" />
            <p className="text-sm">Starting…</p>
          </div>
        ) : (
          <div className="max-w-md bg-surface rounded-xl shadow-sm border border-line p-6 space-y-3">
            <p className="font-medium text-ink">Couldn't start the backend</p>
            <p className="text-sm text-red-600 dark:text-red-400 break-words">{backend.message}</p>
            {/* The shell only launches the backend once, so restart to retry. */}
            <button
              onClick={inTauri ? () => shell.restart() : connect}
              className="bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1.5 rounded-lg text-sm font-medium"
            >
              {inTauri ? "Restart app" : "Retry"}
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-canvas flex">
      <nav className="w-52 bg-slate-900 text-white flex flex-col shrink-0 dark:border-r dark:border-line">
        <div className="px-5 py-5 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center">
            <Wallet size={18} />
          </div>
          <div>
            <h1 className="text-base font-semibold leading-tight">SplitLens</h1>
            <p className="text-xs text-slate-400">Local & private</p>
          </div>
        </div>
        <ul className="flex-1 px-3 space-y-0.5">
          {NAV.map((item) => (
            <li key={item.id}>
              <button
                onClick={() => setPage(item.id)}
                aria-current={page === item.id ? "page" : undefined}
                className={`w-full flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                  page === item.id
                    ? "bg-indigo-600 text-white"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <item.icon size={17} />
                {item.label}
              </button>
            </li>
          ))}
        </ul>
        <ThemeSwitch />
      </nav>

      <main className="flex-1 overflow-auto">
        {page === "dashboard" && <Dashboard onImport={() => setPage("import")} />}
        {page === "budgets" && <Budgets />}
        {page === "transactions" && <Transactions accounts={accounts} onImport={() => setPage("import")} />}
        {page === "accounts" && (
          <Accounts accounts={accounts} onChange={loadAccounts} />
        )}
        {page === "import" && (
          <Import accounts={accounts} />
        )}
        {page === "settings" && <Settings />}
      </main>
    </div>
  );
}

const THEMES: { id: ThemePreference; label: string; icon: LucideIcon }[] = [
  { id: "system", label: "System", icon: Monitor },
  { id: "light", label: "Light", icon: Sun },
  { id: "dark", label: "Dark", icon: Moon },
];

function ThemeSwitch() {
  const [theme, setTheme] = useThemePreference();
  return (
    <div className="p-3 border-t border-slate-700">
      <div className="flex rounded-lg bg-slate-800 p-0.5 text-xs" role="radiogroup" aria-label="Theme">
        {THEMES.map((t) => (
          <button
            key={t.id}
            role="radio"
            aria-checked={theme === t.id}
            onClick={() => setTheme(t.id)}
            title={t.label}
            aria-label={t.label}
            className={`flex-1 flex justify-center rounded-md py-1.5 transition-colors ${
              theme === t.id ? "bg-slate-600 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            <t.icon size={15} />
          </button>
        ))}
      </div>
    </div>
  );
}

export default App;
