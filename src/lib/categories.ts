export const CATEGORIES = [
  { name: "Groceries", color: "#22c55e", icon: "🛒" },
  { name: "Dining", color: "#f97316", icon: "🍽️" },
  { name: "Gas & Transport", color: "#3b82f6", icon: "⛽" },
  { name: "Travel", color: "#8b5cf6", icon: "✈️" },
  { name: "Shopping", color: "#ec4899", icon: "🛍️" },
  { name: "Entertainment", color: "#f59e0b", icon: "🎬" },
  { name: "Health & Fitness", color: "#10b981", icon: "💪" },
  { name: "Pharmacy", color: "#14b8a6", icon: "💊" },
  { name: "Subscriptions", color: "#6366f1", icon: "📱" },
  { name: "Utilities", color: "#64748b", icon: "💡" },
  { name: "Home", color: "#a16207", icon: "🏠" },
  { name: "Personal Care", color: "#db2777", icon: "🧴" },
  { name: "Kids & Pets", color: "#0ea5e9", icon: "🐾" },
  { name: "Education", color: "#7c3aed", icon: "📚" },
  { name: "Insurance", color: "#475569", icon: "🛡️" },
  { name: "ATM/Cash", color: "#854d0e", icon: "💵" },
  { name: "Transfers", color: "#334155", icon: "↔️" },
  { name: "Other", color: "#94a3b8", icon: "•" },
] as const;

export type CategoryName = (typeof CATEGORIES)[number]["name"];

export const categoryColor = (name: string) =>
  CATEGORIES.find((c) => c.name === name)?.color ?? "#94a3b8";

export const categoryIcon = (name: string) =>
  CATEGORIES.find((c) => c.name === name)?.icon ?? "•";
