import { ChevronLeft, ChevronRight } from "lucide-react";
import { monthLabel, shiftMonth, thisMonth } from "../lib/month";
import { buttonGhost } from "./ui";

/** Previous / next month, with a shortcut back to this month. `latest` caps how far forward it goes. */
export function MonthPicker({ month, onChange, latest }: { month: string; onChange: (m: string) => void; latest?: string }) {
  const atLatest = latest !== undefined && month >= latest;
  return (
    <>
      {month !== thisMonth() && (
        <button className={buttonGhost} onClick={() => onChange(thisMonth())}>
          This month
        </button>
      )}
      <button className={buttonGhost} onClick={() => onChange(shiftMonth(month, -1))} aria-label="Previous month">
        <ChevronLeft size={16} />
      </button>
      <span className="text-sm font-medium text-ink min-w-32 text-center">{monthLabel(month)}</span>
      <button
        className={buttonGhost}
        onClick={() => onChange(shiftMonth(month, 1))}
        disabled={atLatest}
        style={atLatest ? { opacity: 0.4 } : undefined}
        aria-label="Next month"
      >
        <ChevronRight size={16} />
      </button>
    </>
  );
}
