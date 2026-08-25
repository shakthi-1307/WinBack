// Cumulative recovery over simulated days, drawn as inline SVG.
// No chart library: one line, one area, one marker.

import { compactRupees } from "../format.js";

const WIDTH = 720;
const HEIGHT = 220;
const PAD = { top: 16, right: 16, bottom: 28, left: 58 };

export function renderChart(root, series, currentDay) {
  if (!series || series.length === 0) {
    root.innerHTML = '<p class="empty">No campaign data yet.</p>';
    return;
  }

  const maxDay = series[series.length - 1].day || 1;
  const maxValue = Math.max(...series.map((p) => p.recovered_rupees), 1);

  const plotWidth = WIDTH - PAD.left - PAD.right;
  const plotHeight = HEIGHT - PAD.top - PAD.bottom;
  const x = (day) => PAD.left + (day / maxDay) * plotWidth;
  const y = (value) => PAD.top + plotHeight - (value / maxValue) * plotHeight;

  const visible = series.filter((p) => p.day <= currentDay);
  const points = (visible.length ? visible : [series[0]])
    .map((p) => `${x(p.day).toFixed(1)},${y(p.recovered_rupees).toFixed(1)}`)
    .join(" ");

  const last = visible[visible.length - 1] || series[0];
  const areaPath =
    `M ${PAD.left},${y(0)} L ` + points.split(" ").join(" L ") +
    ` L ${x(last.day)},${y(0)} Z`;

  const yTicks = [0, 0.5, 1].map((fraction) => {
    const value = maxValue * fraction;
    return `
      <line class="chart-grid" x1="${PAD.left}" y1="${y(value)}"
            x2="${WIDTH - PAD.right}" y2="${y(value)}" />
      <text class="chart-axis" x="${PAD.left - 8}" y="${y(value) + 3.5}"
            text-anchor="end">${compactRupees(value)}</text>`;
  }).join("");

  const xTicks = [0, Math.round(maxDay / 2), maxDay].map(
    (day) => `<text class="chart-axis" x="${x(day)}" y="${HEIGHT - 8}"
                    text-anchor="middle">day ${day}</text>`
  ).join("");

  root.innerHTML = `
    <svg class="chart" viewBox="0 0 ${WIDTH} ${HEIGHT}" role="img"
         aria-label="Cumulative rupees recovered by simulated day">
      ${yTicks}
      ${xTicks}
      <path class="chart-area" d="${areaPath}" />
      <polyline class="chart-line" points="${points}" />
      <line class="chart-today" x1="${x(last.day)}" y1="${PAD.top}"
            x2="${x(last.day)}" y2="${PAD.top + plotHeight}" />
      <circle class="chart-end" cx="${x(last.day)}"
              cy="${y(last.recovered_rupees)}" r="3.5" />
    </svg>`;
}
