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

async function doJoin(selected, inviteCode) {
  const data = await perform(
    () => request(`/api/demo/participants/${selected}/join`, "POST", { invite_code: inviteCode }),
    "join-output",
  );
  if (!data) return;
  participant = selected;
  session = data.participant_session;
  sessionStorage.setItem("hushParticipant", participant);
  sessionStorage.setItem("hushParticipantSession", session);
  showWorkspace();
}

byId("join").onclick = () => doJoin(byId("participant").value, byId("invite-code").value);

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

const STEP_LABELS = {
  createDecision: "1. createDecision (방 생성)",
  finalizeInputSet: "2. finalizeInputSet (입력 집합 고정)",
  commitDecision: "3. commitDecision (최종 결정 커밋)",
};
const STATUS_CLASS = { PENDING: "chain-status-pending", FAILED: "chain-status-failed", UNAVAILABLE: "chain-status-local" };

function renderChain(provenance, verifyResult) {
  const box = byId("chain-box");
  if (!provenance) { box.hidden = true; return; }
  box.hidden = false;

  const status = provenance.status || "UNKNOWN";
  const statusEl = byId("chain-status");
  statusEl.textContent = status;
  statusEl.className = "badge " + (STATUS_CLASS[status] || "");

  const meta = [];
  if (provenance.network) meta.push(provenance.network);
  if (provenance.chain_id) meta.push(`chainId ${provenance.chain_id}`);
  if (provenance.contract_address) meta.push(`contract ${provenance.contract_address}`);
  if (provenance.onchain_decision_commitment) meta.push(`commitment ${provenance.onchain_decision_commitment.slice(0, 18)}…`);
  if (provenance.reason) meta.push(provenance.reason);
  if (provenance.note) meta.push(provenance.note);
  byId("chain-meta").textContent = meta.join(" · ");

  const list = byId("chain-txs");
  list.innerHTML = "";
  const txs = provenance.transactions || [];
  if (status === "PENDING" && txs.length === 0) {
    const li = document.createElement("li");
    li.className = "pending";
    li.textContent = "3개 트랜잭션 전송 대기 중…";
    list.appendChild(li);
  }
  for (const step of ["createDecision", "finalizeInputSet", "commitDecision"]) {
    const tx = txs.find((t) => t.step === step);
    if (!tx) continue;
    const li = document.createElement("li");
    const label = document.createTextNode(`${STEP_LABELS[step]} — ${tx.status}${tx.block_number ? ` · block #${tx.block_number}` : ""} `);
    li.appendChild(label);
    const url = tx.explorer_url;
    if (url) {
      const a = document.createElement("a");
      a.href = url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = tx.tx_hash ? `${tx.tx_hash.slice(0, 14)}…` : "explorer";
      li.appendChild(a);
    } else if (tx.error) {
      li.appendChild(document.createTextNode(`(${tx.error})`));
    }
    list.appendChild(li);
  }

  const v = byId("chain-verify");
  if (verifyResult && verifyResult.onchain) {
    v.hidden = false;
    const ok = verifyResult.onchain.verified;
    v.textContent = ok
      ? "on-chain 재조회: 레지스트리 값이 영수증과 일치합니다 ✓"
      : `on-chain 재조회: ${verifyResult.onchain.note || "일치 확인 실패 / 생략"}`;
    v.className = "chain-verify " + (ok ? "ok" : "bad");
  } else {
    v.hidden = true;
  }
}

byId("receipt").onclick = async () => {
  latestReceipt = await request(`/api/demo/participants/${participant}/receipt`);
  renderChain(latestReceipt.chain_provenance, null);
  byId("receipt-output").textContent = JSON.stringify(latestReceipt, null, 2);
};
byId("verify").onclick = async () => {
  const data = await perform(() => request(`/api/demo/participants/${participant}/verify`, "POST"), "receipt-output");
  if (data) {
    const prov = (latestReceipt && latestReceipt.chain_provenance) || null;
    renderChain(prov, data);
  }
};
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

// QR / link entry: /participant?p=A&code=HUSH-A-2026 → prefill and auto-join.
function initFromQuery() {
  const params = new URLSearchParams(location.search);
  const p = (params.get("p") || "").toUpperCase();
  const code = params.get("code") || "";
  if (["A", "B", "C", "D"].includes(p)) byId("participant").value = p;
  if (code) byId("invite-code").value = code;
  if (["A", "B", "C", "D"].includes(p) && code && !(participant && session)) {
    doJoin(p, code);
  }
}

if (participant && session) {
  showWorkspace();
} else {
  initFromQuery();
}
