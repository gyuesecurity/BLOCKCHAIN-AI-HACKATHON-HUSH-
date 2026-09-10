const byId = (id) => document.getElementById(id);
let participant = sessionStorage.getItem("hushParticipant");
let session = sessionStorage.getItem("hushParticipantSession");
let draftId = null;
let latestReceipt = null;

async function request(path, method = "GET", body = undefined) {
  const headers = { "Content-Type": "application/json" };
  if (session) headers["X-Participant-Session"] = session;
  const response = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || "요청에 실패했습니다.");
  return data;
}

function showWorkspace() {
  byId("join-card").hidden = true;
  byId("workspace").hidden = false;
  byId("owner").textContent = participant;
  refreshPrivate();
}

async function perform(task, target = "private-output") {
  try {
    const data = await task();
    byId(target).textContent = JSON.stringify(data, null, 2);
    return data;
  } catch (error) {
    byId(target).textContent = `ERROR\n${error.message}`;
    return null;
  }
}

async function refreshPrivate() {
  const data = await perform(() => request(`/api/demo/participants/${participant}`));
  const proposal = data?.proposal;
  byId("proposal-box").hidden = !proposal || proposal.status !== "PROPOSED";
  if (proposal) {
    byId("proposal-text").textContent = `${proposal.current_constraint_value.amount.toLocaleString()}원에서 ${proposal.proposed_constraint_value.amount.toLocaleString()}원으로 변경하면 ${proposal.feasible_candidate_count}개의 합의 후보가 생깁니다.`;
  }
}

byId("join").onclick = async () => {
  const selected = byId("participant").value;
  const data = await perform(() => request(`/api/demo/participants/${selected}/join`, "POST", { invite_code: byId("invite-code").value }), "join-output");
  if (!data) return;
  participant = selected;
  session = data.participant_session;
  sessionStorage.setItem("hushParticipant", participant);
  sessionStorage.setItem("hushParticipantSession", session);
  showWorkspace();
};

byId("parse").onclick = async () => {
  const data = await perform(() => request(`/api/demo/participants/${participant}/private-inputs/parse`, "POST", { source_text: byId("source-text").value }), "draft-output");
  if (data) {
    draftId = data.draft_id;
    byId("confirm").disabled = false;
    const mode = data.is_ai
      ? `AI 구조화 · ${data.model || "LLM"}`
      : `규칙 파서${data.llm_fallback ? " (LLM fallback)" : ""}`;
    const priority = data.structured_candidate?.priority;
    const priorityLabel = priority === "SOFT" ? "선호(SOFT)" : "필수(HARD)";
    byId("draft-output").textContent =
      `[${mode} · ${priorityLabel}]\n${data.notice || ""}\n\n` + JSON.stringify(data, null, 2);
  }
};
byId("confirm").onclick = async () => {
  const data = await perform(() => request(`/api/demo/participants/${participant}/constraints/confirm`, "POST", { draft_id: draftId }), "draft-output");
  if (data) { byId("confirm").disabled = true; await refreshPrivate(); }
};
byId("run").onclick = () => perform(() => request(`/api/demo/participants/${participant}/decision-runs`, "POST")).then(refreshPrivate);
byId("refresh").onclick = refreshPrivate;
byId("accept").onclick = () => perform(() => request(`/api/demo/participants/${participant}/proposal/accept`, "POST")).then(refreshPrivate);
byId("reject").onclick = () => perform(() => request(`/api/demo/participants/${participant}/proposal/reject`, "POST")).then(refreshPrivate);
byId("receipt").onclick = async () => {
  latestReceipt = await request(`/api/demo/participants/${participant}/receipt`);
  byId("receipt-output").textContent = JSON.stringify(latestReceipt, null, 2);
};
byId("verify").onclick = () => perform(() => request(`/api/demo/participants/${participant}/verify`, "POST"), "receipt-output");
byId("export").onclick = async () => {
  latestReceipt = await request(`/api/demo/participants/${participant}/receipt/export`);
  const blob = new Blob([JSON.stringify(latestReceipt, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `hush-receipt-${participant}.json`;
  link.click();
  URL.revokeObjectURL(url);
};
byId("logout").onclick = () => {
  sessionStorage.removeItem("hushParticipant");
  sessionStorage.removeItem("hushParticipantSession");
  window.location.reload();
};

if (participant && session) showWorkspace();
