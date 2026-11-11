import { ReactNode } from "react";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 mb-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">{title}</h1>
        {subtitle && <p className="text-sm text-muted mt-1">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ className = "", children }: { className?: string; children: ReactNode }) {
  return <div className={`bg-surface rounded-xl shadow-sm border border-line ${className}`}>{children}</div>;
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
  "inline-flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium px-4 py-2 disabled:opacity-50 transition-colors";
export const buttonGhost =
  "inline-flex items-center justify-center gap-1.5 rounded-lg border border-field text-ink-soft hover:bg-surface-muted text-sm px-3 py-1.5 transition-colors";
export const field = "border border-field rounded-lg px-3 py-2 text-sm";
