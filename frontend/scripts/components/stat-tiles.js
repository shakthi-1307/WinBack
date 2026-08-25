// The four numbers an operator checks first.

import { compactRupees, percent } from "../format.js";

export function renderTiles(root, metrics) {
  if (!metrics) {
    root.innerHTML = "";
    return;
  }

  const tiles = [
    {
      cls: "is-risk",
      label: "Still at risk",
      value: compactRupees(metrics.at_risk_remaining_rupees),
      sub: `of ${compactRupees(metrics.at_risk_rupees)} total`,
    },
    {
      cls: "is-good",
      label: "Recovered",
      value: compactRupees(metrics.recovered_rupees),
      sub: `${metrics.recovered_count} payments · ${percent(metrics.recovery_rate)}`,
    },
    {
      cls: "is-flight",
      label: "In flight",
      value: String(metrics.in_flight),
      sub: `${metrics.charge_attempts} charges · ${metrics.contacts} messages`,
    },
    {
      cls: "is-stop",
      label: "Impossible charges",
      value: String(metrics.impossible_charges),
      sub: "attempts with a 0% chance",
    },
  ];

  root.innerHTML = tiles
    .map(
      (tile) => `
    <div class="tile ${tile.cls}">
      <span class="label">${tile.label}</span>
      <span class="value">${tile.value}</span>
      <span class="sub">${tile.sub}</span>
    </div>`
    )
    .join("");
}
