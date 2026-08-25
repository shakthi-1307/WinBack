// Display formatting. Pure functions, no DOM, no fetching.

const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

export function rupees(value) {
  return `₹${inr.format(Math.round(value || 0))}`;
}

export function compactRupees(value) {
  const amount = Math.round(value || 0);
  if (amount >= 100000) return `₹${(amount / 100000).toFixed(2)}L`;
  if (amount >= 1000) return `₹${(amount / 1000).toFixed(1)}k`;
  return `₹${inr.format(amount)}`;
}

export function percent(fraction) {
  return `${((fraction || 0) * 100).toFixed(1)}%`;
}

export function titleise(text) {
  return String(text || "").replace(/_/g, " ");
}

// Same glyphs the text replay uses, so the console and the CLI tell the
// same story in the same visual language.
const GLYPHS = {
  planned: "·",
  blocked: "✕",
  executed: "→",
  duplicate_suppressed: "=",
  gateway_error: "!",
  recovered: "✓",
  abandoned: "◻",
  hostile_note_seen: "⚑",
};

export function glyphFor(eventType) {
  return GLYPHS[eventType] || "·";
}
