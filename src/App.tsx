import { useEffect, useState } from "react";
import { db, Account } from "./lib/db";
import { Dashboard } from "./pages/Dashboard";
import { Transactions } from "./pages/Transactions";
import { Cards } from "./pages/Cards";
import { Import } from "./pages/Import";

type Page = "dashboard" | "transactions" | "cards" | "import";

const NAV: { id: Page; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "transactions", label: "Transactions" },
  { id: "cards", label: "Cards" },
  { id: "import", label: "Import" },
];

function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [accounts, setAccounts] = useState<Account[]>([]);

  const loadAccounts = () => db.getAccounts().then(setAccounts);

  useEffect(() => {
    loadAccounts();
  }, []);

  return (
    <div className="min-h-screen bg-slate-100 flex">
      <nav className="w-52 bg-slate-900 text-white flex flex-col shrink-0">
        <div className="px-5 py-5 border-b border-slate-700">
          <h1 className="text-lg font-semibold">Finance</h1>
          <p className="text-xs text-slate-400 mt-0.5">Local & private</p>
        </div>
        <ul className="flex-1 py-3">
          {NAV.map((item) => (
            <li key={item.id}>
              <button
                onClick={() => setPage(item.id)}
                className={`w-full text-left px-5 py-2.5 text-sm transition-colors ${
                  page === item.id
                    ? "bg-indigo-600 text-white"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <main className="flex-1 overflow-auto">
        {page === "dashboard" && <Dashboard />}
        {page === "transactions" && <Transactions />}
        {page === "cards" && (
          <Cards accounts={accounts} onChange={loadAccounts} />
        )}
        {page === "import" && (
          <Import
            accounts={accounts
              .filter((a) => a.id != null)
              .map((a) => ({ id: a.id!, name: a.name }))}
          />
        )}
      </main>
    </div>
  );
}

export default App;
