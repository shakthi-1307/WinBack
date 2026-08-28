// When the agent decided to act — the timing thesis, made visible.
//
// Form: a calendar heatmap rather than a bar chart, because the argument IS
// the calendar structure. Attempts clustering on the 1st and 7th means
// nothing unless you can see that those are the days people get paid.
//
// Colour does three separate jobs and never mixes them:
//   magnitude  — attempt volume, one hue light→dark (sequential)
//   status     — money actually recovered, the good green
//   structure  — payday is a property of the calendar, not of the data, so
//                it is marked with a rule and a label, never a rival hue

import { compactRupees } from "../format.js";

const DAYS = 30;
const STEPS = [0.14, 0.3, 0.48, 0.68, 0.9];

function stepFor(fired, max) {
  if (!fired) return 0;
  const ratio = max > 0 ? fired / max : 0;
  return STEPS[Math.min(STEPS.length - 1, Math.floor(ratio * STEPS.length))];
}

function intensity(step) {
  if (!step) return "var(--surface)";
  return `color-mix(in oklab, var(--accent) ${Math.round(step * 100)}%, var(--surface))`;
}

// Past roughly half strength the fill is dark enough that ink-coloured text
// disappears into it. A sequential ramp has to carry its labels the whole way,
// so the text flips rather than the ramp being cut short.
const INK_FLIPS_AT = 0.45;

function tooltip(cell) {
  const parts = [`Day ${cell.day}`];
  if (cell.is_payday) parts.push(`payday for ${cell.payday_customers} customers`);
  else if (cell.in_payday_window) parts.push("inside a payday window");
  parts.push(`${cell.charges} charges, ${cell.contacts} messages`);
  if (cell.recovered) {
    parts.push(`${cell.recovered} recovered (${compactRupees(cell.recovered_rupees)})`);
  }
  if (cell.scheduled) parts.push(`${cell.scheduled} still scheduled`);
  return parts.join(" · ");
}

export function renderCalendar(root, calendar) {
  if (!calendar || !calendar.days) {
    root.innerHTML = '<p class="empty">No campaign data yet.</p>';
    return;
  }

  const max = calendar.max_fired || 1;

  const cells = calendar.days
    .map((cell) => {
      const step = stepFor(cell.fired, max);
      const classes = ["cal-cell"];
      if (step >= INK_FLIPS_AT) classes.push("on-dark");
      if (cell.is_payday) classes.push("is-payday");
      else if (cell.in_payday_window) classes.push("in-window");
      if (cell.scheduled) classes.push("has-scheduled");

      const recovered = cell.recovered
        ? `<span class="cal-recovered">${cell.recovered}</span>`
        : "";
      const scheduled = cell.scheduled
        ? `<span class="cal-scheduled">${cell.scheduled} due</span>`
        : "";
      const flag = cell.is_payday ? '<span class="cal-flag">payday</span>' : "";

      return `
        <div class="${classes.join(" ")}"
             style="--fill: ${intensity(step)}"
             tabindex="0"
             title="${tooltip(cell)}">
          <span class="cal-day">${cell.day}</span>
          ${flag}
          <span class="cal-count">${cell.fired || ""}</span>
          ${recovered}
          ${scheduled}
        </div>`;
    })
    .join("");

  const targeting = Math.round((calendar.timing_payday_targeting || 0) * 100);
  const inWindow = calendar.timing_charges_in_payday_window || 0;
  const total = calendar.timing_charges_total || 0;

  root.innerHTML = `
    <p class="cal-headline">
      <b>${targeting}%</b> of retries on <em>insufficient funds</em> failures land in a
      payday window — ${inWindow} of ${total}. Paydays and their windows cover 13 of
      30 days, so a strategy that ignores timing scores about 43% here by chance.
    </p>
    <div class="cal-grid">${cells}</div>
    <div class="cal-legend">
      <span class="cal-key"><i class="swatch-scale"></i> attempts, light to dark</span>
      <span class="cal-key"><i class="swatch-recovered"></i> recovered that day</span>
      <span class="cal-key"><i class="swatch-payday"></i> payday</span>
      <span class="cal-key"><i class="swatch-scheduled"></i> still scheduled</span>
    </div>`;
}
