// A tiny observable store. One source of truth, subscribers re-render.

const listeners = new Set();

const state = {
  status: null,
  metrics: null,
  series: [],
  transactions: [],
  guardrails: null,
  selected: null,
  replay: null,
  filter: null,
  running: false,
};

export function getState() {
  return state;
}

export function setState(patch) {
  Object.assign(state, patch);
  listeners.forEach((listener) => listener(state));
}

export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
