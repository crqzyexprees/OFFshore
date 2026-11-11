/** "$1,234.5" → 123450; blank or zero → null; anything else → undefined (not an amount). */
export function parseDollars(text: string): number | null | undefined {
  const cleaned = text.replace(/[$,\s]/g, "");
  if (cleaned === "") return null;
  if (!/^\d+(\.\d{0,2})?$/.test(cleaned)) return undefined;
  const cents = Math.round(Number(cleaned) * 100);
  return cents === 0 ? null : cents;
}

/** 123450 → "1234.5"; null → "". For editing amounts in inputs. */
export const dollars = (cents: number | null) => (cents == null ? "" : (cents / 100).toFixed(2).replace(/\.00$/, ""));

/** Today as YYYY-MM-DD in local time. */
export const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

/** Splits `cents` into `parts` whole-cent pieces that add up exactly; the first takes any remainder. */
export function splitEvenly(cents: number, parts: number): number[] {
  const each = Math.floor(cents / parts);
  return Array.from({ length: parts }, (_, i) => each + (i === 0 ? cents - each * parts : 0));
}
