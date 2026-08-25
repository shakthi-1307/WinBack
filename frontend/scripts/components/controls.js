// Campaign controls, including a kill switch an operator can actually reach.

export function renderControls(root, { status, running, strategies }, handlers) {
  const finished = status?.finished;
  const options = (strategies || [])
    .map(
      (name) =>
        `<option value="${name}"${name === status?.strategy ? " selected" : ""}>${name}</option>`
    )
    .join("");

  root.innerHTML = `
    <select id="strategy" aria-label="Strategy">${options}</select>
    <button id="run" class="primary" ${running || finished ? "disabled" : ""}>
      ${running ? "Running…" : "Run campaign"}
    </button>
    <button id="step" ${running || finished ? "disabled" : ""}>Step one day</button>
    <button id="reset">Reset</button>
    <button id="kill" class="danger" ${running ? "" : "disabled"}>Kill switch</button>
    <span class="clock">day <b>${status ? Math.min(status.day, status.horizon) : 0}</b>
      / ${status?.horizon ?? 21}${status?.killed ? " · STOPPED" : ""}</span>`;

  root.querySelector("#run").onclick = handlers.onRun;
  root.querySelector("#step").onclick = handlers.onStep;
  root.querySelector("#reset").onclick = handlers.onReset;
  root.querySelector("#kill").onclick = handlers.onKill;
  root.querySelector("#strategy").onchange = (event) =>
    handlers.onStrategy(event.target.value);
}
