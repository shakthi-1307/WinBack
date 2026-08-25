// Every network call the console makes. Nothing else lives here.

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`${options.method || "GET"} ${path} failed: ${response.status}`);
  }
  return response.json();
}

export const api = {
  health: () => request("/api/health"),
  status: () => request("/api/campaign/status"),
  strategies: () => request("/api/campaign/strategies"),
  reset: (strategy, size) =>
    request("/api/campaign/reset", {
      method: "POST",
      body: JSON.stringify({ strategy, size }),
    }),
  tick: () => request("/api/campaign/tick", { method: "POST" }),
  runAll: () => request("/api/campaign/run", { method: "POST" }),
  kill: () => request("/api/campaign/kill", { method: "POST" }),
  metrics: () => request("/api/metrics"),
  timeseries: () => request("/api/metrics/timeseries"),
  transactions: (status) =>
    request(`/api/transactions${status ? `?status=${status}` : ""}`),
  replay: (id) => request(`/api/transactions/${id}`),
  guardrails: () => request("/api/guardrails"),
};
