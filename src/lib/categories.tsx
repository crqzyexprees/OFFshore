import {
  BookOpen, Car, Circle, Clapperboard, HeartPulse, House, Lightbulb, LucideIcon, PawPrint,
  Pill, Plane, Receipt, Repeat, Shield, ShoppingBag, ShoppingCart, Sofa, Sparkles, Utensils,
} from "lucide-react";

// Presentation only: the Category list itself comes from the backend.
const STYLES: Record<string, { color: string; icon: LucideIcon }> = {
  Dining: { color: "#f97316", icon: Utensils },
  Education: { color: "#7c3aed", icon: BookOpen },
  Entertainment: { color: "#f59e0b", icon: Clapperboard },
  "Fees & Interest": { color: "#b91c1c", icon: Receipt },
  Groceries: { color: "#22c55e", icon: ShoppingCart },
  Health: { color: "#10b981", icon: HeartPulse },
  Home: { color: "#a16207", icon: Sofa },
  Housing: { color: "#0f766e", icon: House },
  Insurance: { color: "#475569", icon: Shield },
  "Kids & Pets": { color: "#0ea5e9", icon: PawPrint },
  Other: { color: "#94a3b8", icon: Circle },
  "Personal Care": { color: "#db2777", icon: Sparkles },
  Pharmacy: { color: "#14b8a6", icon: Pill },
  Shopping: { color: "#ec4899", icon: ShoppingBag },
  Subscriptions: { color: "#6366f1", icon: Repeat },
  Transport: { color: "#3b82f6", icon: Car },
  Travel: { color: "#8b5cf6", icon: Plane },
  Utilities: { color: "#64748b", icon: Lightbulb },
};

export const categoryColor = (name: string) => STYLES[name]?.color ?? "#94a3b8";

/** The Category's icon on a tinted circle in its colour. */
export function CategoryIcon({ name, size = 28 }: { name: string; size?: number }) {
  const { color, icon: Icon } = STYLES[name] ?? STYLES.Other;
  return (
    <span
      className="inline-flex items-center justify-center rounded-full shrink-0"
      style={{ width: size, height: size, backgroundColor: `${color}26`, color }}
    >
      <Icon size={Math.round(size * 0.55)} strokeWidth={2} />
    </span>
  );
}
