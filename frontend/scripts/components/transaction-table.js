// Every transaction, its reason code, and where it got to.

import { rupees, titleise } from "../format.js";

const COLUMNS = ["txn", "amount", "reason code", "status", "att", "last action", "day"];

export function renderTable(root, transactions, selectedId, onSelect) {
  if (!transactions || transactions.length === 0) {
    root.innerHTML = '<p class="empty">No transactions match this filter.</p>';
    return;
  }

  const head = COLUMNS.map((c) => `<th>${c}</th>`).join("");
  const rows = transactions
    .map((txn) => {
      const selected = txn.id === selectedId ? ' aria-selected="true"' : "";
      const day = txn.recovered_on_day !== null ? txn.recovered_on_day : "—";
      return `
        <tr data-id="${txn.id}" tabindex="0"${selected}>
          <td class="code">${txn.id}</td>
          <td class="num">${rupees(txn.amount_rupees)}</td>
          <td class="code">${txn.reason_code}</td>
          <td><span class="pill ${txn.status}">${titleise(txn.status)}</span></td>
          <td class="num">${txn.attempts}</td>
          <td class="code">${txn.last_action ? titleise(txn.last_action) : "—"}</td>
          <td class="num">${day}</td>
        </tr>`;
    })
    .join("");

  root.innerHTML = `
    <div class="table-scroll">
      <table>
        <thead><tr>${head}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;

  root.querySelectorAll("tbody tr").forEach((row) => {
    const open = () => onSelect(row.dataset.id);
    row.addEventListener("click", open);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
  });
}
