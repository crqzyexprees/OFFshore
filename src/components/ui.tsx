import { ReactNode } from "react";

/** Title, one-line description, and the page's controls on the right. */
export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">{title}</h1>
        {subtitle && <p className="text-sm text-muted mt-1">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/** A card's heading row, with optional controls on the right. */
export function CardTitle({ children, actions }: { children: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
      <h2 className="text-lg font-semibold text-ink">{children}</h2>
      {actions}
    </div>
  );
}

/** A label, a large figure, and a caption: the summary tiles at the top of a page. */
export function Stat({ label, value, caption, tone }: { label: ReactNode; value: ReactNode; caption?: ReactNode; tone?: "bad" | "good" }) {
  const color = tone === "bad" ? "text-red-600 dark:text-red-400" : tone === "good" ? "text-emerald-700 dark:text-emerald-400" : "text-ink";
  return (
    <Card className="p-5">
      <p className="text-sm text-muted">{label}</p>
      <p className={`text-3xl font-bold tabular-nums mt-2 ${color}`}>{value}</p>
      {caption && <p className="text-sm text-muted mt-2">{caption}</p>}
    </Card>
  );
}

export function Card({ className = "", children }: { className?: string; children: ReactNode }) {
  return <div className={`bg-surface rounded-2xl shadow-sm border border-line ${className}`}>{children}</div>;
}

/** A friendly placeholder for when a list or chart has nothing to show. */
export function EmptyState({ icon, title, hint, action }: { icon: ReactNode; title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 px-6 gap-2">
      <div className="text-faint mb-1">{icon}</div>
      <p className="font-medium text-ink-soft">{title}</p>
      {hint && <p className="text-sm text-muted max-w-sm">{hint}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export const buttonPrimary =
  "inline-flex items-center justify-center gap-2 bg-accent hover:bg-accent-hover text-accent-ink rounded-lg text-sm font-medium px-4 py-2 transition-colors";
export const buttonGhost =
  "inline-flex items-center justify-center gap-1.5 rounded-lg border border-line bg-surface text-ink hover:border-field hover:bg-surface-muted text-sm px-3 py-2 transition-colors";
export const field = "border border-line rounded-lg px-3 py-2 text-sm";
