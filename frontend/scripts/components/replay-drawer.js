// One transaction's whole story, rebuilt from the ledger.
//
// Nothing here is a summary written afterwards — every line was appended at
// the moment it happened.

import { glyphFor, rupees, titleise } from "../format.js";

export function renderDrawer(elements, replay, onClose) {
  const { backdrop, drawer, title, body } = elements;

  if (!replay) {
    backdrop.classList.remove("open");
    drawer.classList.remove("open");
    return;
  }

  const txn = replay.transaction;
  backdrop.classList.add("open");
  drawer.classList.add("open");
  title.textContent = txn.id;

  const meta = [
    ["amount", rupees(txn.amount_rupees)],
    ["reason", txn.reason_code],
    ["class", titleise(txn.failure_class)],
    ["status", titleise(txn.status)],
    ["mandate", txn.mandate_valid ? "valid" : "revoked"],
    ["customer", txn.dnd ? "DND registered" : `payday ${txn.payday}`],
  ]
    .map(([k, v]) => `<div><span class="k">${k}</span>${v}</div>`)
    .join("");

  const note = replay.support_note
    ? `<div class="hostile">
         <span class="tag">account note — untrusted input</span>
         <blockquote>${escapeHtml(replay.support_note)}</blockquote>
       </div>`
    : "";

  const timeline = replay.timeline
    .map(
      (event) => `
    <li class="${event.type}">
      <span class="glyph">${glyphFor(event.type)}</span>
      <span class="day">day ${event.day}</span>
      <span class="text">${escapeHtml(event.text)}</span>
    </li>`
    )
    .join("");

  body.innerHTML = `
    <div class="meta-grid">${meta}</div>
    ${note}
    <ul class="timeline">${timeline || '<li class="empty">No events.</li>'}</ul>`;

  backdrop.onclick = onClose;
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
