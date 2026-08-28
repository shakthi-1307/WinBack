// Wiring. Fetches and dispatches; holds no rendering logic of its own.

import { api } from "./api.js";
import { renderControls } from "./components/controls.js";
import { renderGuardrails } from "./components/guardrail-panel.js";
import { renderCalendar } from "./components/retry-calendar.js";
import { renderChart } from "./components/recovery-chart.js";
import { renderDrawer } from "./components/replay-drawer.js";
import { renderTiles } from "./components/stat-tiles.js";
import { renderTable } from "./components/transaction-table.js";
import { getState, setState, subscribe } from "./state.js";

// Days advance one at a time with a short pause, so a 21-day campaign is
// something you watch rather than a progress bar that finishes instantly.
const DAY_DELAY_MS = 260;

const el = {
  controls: document.getElementById("controls"),
  tiles: document.getElementById("tiles"),
  chart: document.getElementById("chart"),
  calendar: document.getElementById("calendar"),
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
let health = null;

// The mode line describes what the run ACTUALLY did, measured from the
// executor — never what happens to be configured. A console that claims
// live Razorpay while its attempts went to a double is exactly the
// overstatement this project says is impossible.
function describeMode(status) {
  if (!health) return "connecting…";
  const live = status?.live_gateway_calls || 0;
  const doubled = status?.doubled_gateway_calls || 0;

  let gateway;
  if (live && doubled) gateway = `${live} live razorpay calls, ${doubled} via transport double`;
  else if (live) gateway = `${live} live razorpay calls`;
  else if (doubled) gateway = `${doubled} gateway calls via transport double, 0 live`;
  else if ((status?.live_sample ?? 0) === 0) gateway = "transport double (no live calls this run)";
  else gateway = "razorpay test mode, no charges yet";

  return `model: ${health.model} · gateway: ${gateway}`;
}

async function refresh() {
  const state = getState();
  const [status, metrics, series, transactions, guardrails, calendar] =
    await Promise.all([
      api.status(),
      api.metrics(),
      api.timeseries(),
      api.transactions(state.filter),
      api.guardrails(),
      api.calendar(),
    ]);
  setState({
    status,
    metrics,
    series: series.series,
    transactions: transactions.transactions,
    guardrails,
    calendar,
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
    while (!getState().status?.finished) {
      const status = await api.tick();
      setState({ status });
      await refresh();
      await new Promise((resolve) => setTimeout(resolve, DAY_DELAY_MS));
    }
    setState({ running: false });
  },
  async onStep() {
    await api.tick();
    await refresh();
  },
  async onReset() {
    setState({ running: false, selected: null, replay: null });
    await api.reset(getState().status?.strategy, undefined,
                    getState().status?.live_sample ?? 0);
    await refresh();
  },
  async onKill() {
    await api.kill();
    setState({ running: false });
    await refresh();
  },
  async onStrategy(name) {
    setState({ running: false, selected: null, replay: null });
    await api.reset(name, undefined, getState().status?.live_sample ?? 0);
    await refresh();
  },
  async onLiveSample(sample) {
    setState({ running: false, selected: null, replay: null });
    await api.reset(getState().status?.strategy, undefined, sample);
    await refresh();
  },
};

subscribe((state) => {
  renderControls(el.controls, { ...state, strategies }, handlers);
  renderTiles(el.tiles, state.metrics);
  renderChart(el.chart, state.series, state.status?.day ?? 0);
  renderCalendar(el.calendar, state.calendar);
  renderTable(el.table, state.transactions, state.selected, select);
  renderGuardrails(el.guardrails, state.guardrails);
  renderDrawer(el, state.replay, closeDrawer);
  el.mode.textContent = describeMode(state.status);
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
  const [healthBody, list] = await Promise.all([api.health(), api.strategies()]);
  health = healthBody;
  strategies = list.strategies;
  await api.reset("winback_agent");
  await refresh();
})();
