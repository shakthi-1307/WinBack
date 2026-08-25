// Wiring. Fetches, holds no rendering logic of its own.

import { api } from "./api.js";
import { renderControls } from "./components/controls.js";
import { renderGuardrails } from "./components/guardrail-panel.js";
import { renderChart } from "./components/recovery-chart.js";
import { renderDrawer } from "./components/replay-drawer.js";
import { renderTiles } from "./components/stat-tiles.js";
import { renderTable } from "./components/transaction-table.js";
import { getState, setState, subscribe } from "./state.js";

// Days are advanced one at a time with a short pause, so a 21-day campaign
// is something you watch rather than a progress bar that finishes instantly.
const DAY_DELAY_MS = 260;

const el = {
  controls: document.getElementById("controls"),
  tiles: document.getElementById("tiles"),
  chart: document.getElementById("chart"),
  table: document.getElementById("table"),
  guardrails: document.getElementById("guardrails"),
  filters: document.getElementById("filters"),
  mode: document.getElementById("mode"),
  backdrop: document.getElementById("drawer-backdrop"),
  drawer: document.getElementById("drawer"),
  title: document.getElementById("drawer-title"),
  body: document.getElementById("drawer-body"),
  close: document.getElementById("drawer-close"),
};

let strategies = [];

async function refresh() {
  const state = getState();
  const [status, metrics, series, transactions, guardrails] = await Promise.all([
    api.status(),
    api.metrics(),
    api.timeseries(),
    api.transactions(state.filter),
    api.guardrails(),
  ]);
  setState({
    status,
    metrics,
    series: series.series,
    transactions: transactions.transactions,
    guardrails,
  });
}

async function select(id) {
  const replay = await api.replay(id);
  setState({ selected: id, replay });
}

function closeDrawer() {
  setState({ selected: null, replay: null });
}

const handlers = {
  async onRun() {
    setState({ running: true });
    let status = getState().status;
    while (status && !status.finished) {
      status = await api.tick();
      setState({ status });
      await refresh();
      await new Promise((resolve) => setTimeout(resolve, DAY_DELAY_MS));
      status = getState().status;
    }
    setState({ running: false });
  },
  async onStep() {
    await api.tick();
    await refresh();
  },
  async onReset() {
    setState({ running: false, selected: null, replay: null });
    await api.reset(getState().status?.strategy);
    await refresh();
  },
  async onKill() {
    await api.kill();
    setState({ running: false });
    await refresh();
  },
  async onStrategy(name) {
    setState({ running: false, selected: null, replay: null });
    await api.reset(name);
    await refresh();
  },
};

subscribe((state) => {
  renderControls(el.controls, { ...state, strategies }, handlers);
  renderTiles(el.tiles, state.metrics);
  renderChart(el.chart, state.series, state.status?.day ?? 0);
  renderTable(el.table, state.transactions, state.selected, select);
  renderGuardrails(el.guardrails, state.guardrails);
  renderDrawer(el, state.replay, closeDrawer);
});

el.filters.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-filter]");
  if (!button) return;
  const value = button.dataset.filter || null;
  setState({ filter: value === "all" ? null : value });
  el.filters.querySelectorAll("button").forEach((b) =>
    b.classList.toggle("primary", b === button)
  );
  await refresh();
});

el.close.addEventListener("click", closeDrawer);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeDrawer();
});

(async function start() {
  const [health, list] = await Promise.all([api.health(), api.strategies()]);
  strategies = list.strategies;
  el.mode.textContent = `model: ${health.model} · gateway: ${health.gateway}`;
  await api.reset("winback_agent");
  await refresh();
})();
