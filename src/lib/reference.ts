import { useEffect, useState } from "react";
import { db, Kind, Reference } from "./db";

let cached: Promise<Reference> | null = null;

/** Banks, Transaction kinds and Categories, as the backend defines them. */
export function useReference(): Reference | null {
  const [reference, setReference] = useState<Reference | null>(null);
  useEffect(() => {
    cached ??= db.getReference().catch((e) => {
      cached = null;
      throw e;
    });
    cached.then(setReference, () => {});
  }, []);
  return reference;
}

const nameIn = (list: { id: string; name: string }[] | undefined, id: string) =>
  list?.find((item) => item.id === id)?.name ?? id;

export const kindName = (reference: Reference | null, kind: Kind) => nameIn(reference?.kinds, kind);

export const accountKindName = (reference: Reference | null, kind: string) =>
  nameIn(reference?.account_kinds, kind);

export const bankName = (reference: Reference | null, bank: string | null) =>
  bank ? nameIn(reference?.banks, bank) : "Unknown bank";

/** Whether Transactions of this kind have a Category (and count as Spending). */
export const hasCategory = (reference: Reference | null, kind: Kind) =>
  reference?.categorized_kinds.includes(kind) ?? false;

export const formatMoney = (cents: number) =>
  `${cents < 0 ? "−" : ""}$${(Math.abs(cents) / 100).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
