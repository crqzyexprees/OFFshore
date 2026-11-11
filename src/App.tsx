import { useEffect, useState } from "react";
import { db, Account } from "./lib/db";
import { connectBackend, inTauri, reportUiReady, shell } from "./lib/backend";
import { Dashboard } from "./pages/Dashboard";
import { Transactions } from "./pages/Transactions";
import { Accounts } from "./pages/Accounts";
import { Statements } from "./pages/Statements";
import { Settings } from "./pages/Settings";
import { Budgets } from "./pages/Budgets";
import { ThemePreference, useThemePreference } from "./lib/theme";
import { LucideIcon, Monitor, Moon, Sun } from "lucide-react";

type Page = "dashboard" | "personal" | "budgeting" | "statements" | "accounts" | "settings";

const NAV: { id: Page; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "personal", label: "Personal" },
  { id: "budgeting", label: "Budgeting" },
  { id: "statements", label: "Statements" },
  { id: "accounts", label: "Accounts" },
  { id: "settings", label: "Settings" },
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
            <div className="w-8 h-8 border-4 border-field border-t-ink rounded-full animate-spin" />
            <p className="text-sm">Starting…</p>
          </div>
        ) : (
          <div className="max-w-md bg-surface rounded-xl shadow-sm border border-line p-6 space-y-3">
            <p className="font-medium text-ink">Couldn't start the backend</p>
            <p className="text-sm text-red-600 dark:text-red-400 break-words">{backend.message}</p>
            {/* The shell only launches the backend once, so restart to retry. */}
            <button
              onClick={inTauri ? () => shell.restart() : connect}
              className="bg-accent hover:bg-accent-hover text-accent-ink px-3 py-1.5 rounded-lg text-sm font-medium"
            >
              {inTauri ? "Restart app" : "Retry"}
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-canvas">
      <header className="sticky top-0 z-30 border-b border-zinc-800 bg-black/95 text-white backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4">
          <button onClick={() => setPage("dashboard")} className="flex shrink-0 items-center gap-2 text-sm font-semibold">
            <Logo />
            SplitLens
          </button>
          <nav className="no-scrollbar flex min-w-0 flex-1 items-center gap-1 overflow-x-auto text-sm text-zinc-400">
            {NAV.map((item) => (
              <button
                key={item.id}
                onClick={() => setPage(item.id)}
                aria-current={page === item.id ? "page" : undefined}
                className={`shrink-0 rounded-md px-2.5 py-1.5 leading-none transition-colors ${
                  page === item.id ? "bg-zinc-800 font-medium text-white" : "hover:bg-zinc-900 hover:text-white"
                }`}
              >
                {item.label}
              </button>
            ))}
          </nav>
          <ThemeSwitch />
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        {page === "dashboard" && <Dashboard onImport={() => setPage("statements")} />}
        {page === "personal" && <Transactions accounts={accounts} onImport={() => setPage("statements")} />}
        {page === "budgeting" && <Budgets />}
        {page === "statements" && <Statements accounts={accounts} />}
        {page === "accounts" && <Accounts accounts={accounts} onChange={loadAccounts} />}
        {page === "settings" && <Settings />}
      </main>
    </div>
  );
}

/** Two bars, one bright and one dim: a split. */
function Logo() {
  return (
    <span className="flex h-7 w-7 items-center justify-center rounded-md border border-zinc-700 bg-zinc-950 shadow-sm">
      <span className="relative block h-4 w-4">
        <span className="absolute left-0 top-0 h-4 w-1.5 rounded-full bg-white" />
        <span className="absolute right-0 top-0 h-4 w-1.5 rounded-full bg-zinc-500" />
      </span>
    </span>
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
    <div className="flex shrink-0 rounded-md border border-zinc-700 bg-zinc-950 p-0.5" role="radiogroup" aria-label="Theme">
      {THEMES.map((t) => (
        <button
          key={t.id}
          role="radio"
          aria-checked={theme === t.id}
          onClick={() => setTheme(t.id)}
          title={`${t.label} theme`}
          aria-label={`${t.label} theme`}
          className={`flex h-7 w-7 items-center justify-center rounded transition-colors ${
            theme === t.id ? "bg-zinc-800 text-white" : "text-zinc-500 hover:text-white"
          }`}
        >
          <t.icon size={14} />
        </button>
      ))}
    </div>
  );
}

export default App;
