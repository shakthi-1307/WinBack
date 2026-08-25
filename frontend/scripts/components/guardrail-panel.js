// What the policy engine refused, and what hostile input was seen.
//
// An agent that was stopped is more informative than one that succeeded,
// so this panel gets equal billing with the money.

export function renderGuardrails(root, guardrails) {
  if (!guardrails) {
    root.innerHTML = "";
    return;
  }

  const rules = Object.entries(guardrails.blocks_by_rule || {});
  const ruleRows = rules.length
    ? rules
        .sort((a, b) => b[1] - a[1])
        .map(
          ([rule, count]) =>
            `<div class="rule-row"><code>${rule}</code>
               <span class="count">${count}</span></div>`
        )
        .join("")
    : '<p class="empty">No actions blocked yet.</p>';

  const integrity = `
    <div class="rule-row">
      <span>Gateway errors re-presented</span>
      <span class="count">${guardrails.gateway_errors}</span>
    </div>
    <div class="rule-row">
      <span>Duplicate charges suppressed</span>
      <span class="count">${guardrails.duplicates_suppressed}</span>
    </div>
    <div class="rule-row">
      <span>Hostile account notes seen</span>
      <span class="count">${guardrails.hostile_count}</span>
    </div>`;

  const sample = (guardrails.hostile_notes || []).slice(0, 2);
  const hostile = sample.length
    ? sample
        .map(
          (item) => `
      <div class="hostile">
        <span class="tag">${item.txn_id} — ${item.classes.join(", ")}</span>
        <blockquote>${escapeHtml(item.note)}</blockquote>
      </div>`
        )
        .join("")
    : "";

  root.innerHTML = ruleRows + integrity + hostile;
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
