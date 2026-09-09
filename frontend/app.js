const output = document.querySelector("#output");
const status = document.querySelector("#room-status");
const title = document.querySelector("#room-title");

async function request(path, method = "GET") {
  const headers = path.includes("/participants/A")
    ? { "X-Participant-Session": "demo-session-a" }
    : {};
  const response = await fetch(path, { method, headers });
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || "요청에 실패했습니다.");
  return data;
}

function show(data) {
  output.textContent = JSON.stringify(data, null, 2);
  refresh();
}

async function refresh() {
  const state = await request("/api/demo/state");
  title.textContent = state.title;
  status.textContent = state.status;
}

async function action(task) {
  try { show(await task()); } catch (error) { output.textContent = `ERROR\n${error.message}`; }
}

document.querySelector("#seed").onclick = () => action(() => request("/api/demo/seed-confirmed-inputs", "POST"));
document.querySelector("#run").onclick = () => action(() => request("/api/demo/decision-runs", "POST"));
document.querySelector("#proposal").onclick = () => action(async () => {
  const view = await request("/api/demo/participants/A");
  if (!view.proposal) return view;
  const accepted = window.confirm(`비공개 제안: 예산을 ${view.proposal.current_constraint_value.amount.toLocaleString()}원에서 ${view.proposal.proposed_constraint_value.amount.toLocaleString()}원으로 변경할까요?`);
  if (!accepted) return request("/api/demo/participants/A/proposal/reject", "POST");
  const approval = await request("/api/demo/participants/A/proposal/accept", "POST");
  const recalculation = await request("/api/demo/decision-runs", "POST");
  return { approval, recalculation };
});
document.querySelector("#verify").onclick = () => action(async () => ({
  receipt: await request("/api/demo/participants/A/receipt"),
  verification: await request("/api/demo/participants/A/verify", "POST"),
}));
document.querySelector("#reset").onclick = () => action(() => request("/api/demo/reset", "POST"));

refresh().catch((error) => { output.textContent = error.message; });
