const byId = (id) => document.getElementById(id);
let participant = sessionStorage.getItem("hushParticipant");
let session = sessionStorage.getItem("hushParticipantSession");
let draftId = null;
let latestReceipt = null;
const UI = window.HushUI;

const SUMMARY_TARGET = {
  "join-output": "join-summary",
  "draft-output": "draft-summary",
  "private-output": "private-summary",
  "receipt-output": "receipt-summary",
};

function renderFailure(debugTarget, error) {
  const target = byId(SUMMARY_TARGET[debugTarget]);
  if (target) UI.render(target, [UI.card("요청을 완료하지 못했어요", "다시 확인해 주세요", error.message, "warn")]);
}

function renderPrivateState(data) {
  const participantState = data.participant || {};
  const [participantTitle, participantBody] = UI.status(participantState.input_status || participantState.status);
  const history = data.constraint_version_history || [];
  const active = history.filter((item) => item.status === "ACTIVE");
  const cards = [
    UI.card("내 참여 상태", participantTitle, participantBody, participantState.input_status === "INPUT_CONFIRMED" ? "good" : ""),
    UI.card("확정한 조건", `${active.length}개`, active.length ? "현재 결정에 사용되는 내 조건입니다." : "아직 확정된 조건이 없습니다."),
    ...active.map((item) => UI.card(
      `${UI.typeLabel(item.constraint_type)} · ${item.priority === "HARD" ? "필수" : "선호"}`,
      UI.constraintValue(item.constraint_type, item.constraint_value),
      `조건 버전 ${item.constraint_version}`,
    )),
  ];
  if (data.proposal?.status === "PROPOSED") cards.unshift(UI.card("내 확인이 필요해요", "비공개 조건 조정 제안", "아래 제안을 확인하고 직접 선택해 주세요.", "warn"));
  UI.render(byId("private-summary"), cards);
}

function renderDraft(data) {
  const item = data.structured_candidate || data.constraint || {};
  const parser = data.is_ai ? `AI 구조화 · ${data.model || "LLM"}` : "규칙 기반 구조화";
  UI.render(byId("draft-summary"), [
    UI.card("해석 방식", parser, data.notice || "확정하기 전에 내용을 직접 확인해 주세요."),
    item.constraint_type && UI.card(
      `${UI.typeLabel(item.constraint_type)} · ${item.priority === "SOFT" ? "선호" : "필수"}`,
      UI.constraintValue(item.constraint_type, item.constraint_value),
      item.explanation || "이 내용으로 조건을 확정할 수 있습니다.",
      "good",
    ),
  ]);
}

function renderReceipt(data, verified = false) {
  const candidate = data.candidate || data.final_candidate || {};
  const status = data.status || (verified ? "VERIFIED" : "AVAILABLE");
  const ok = status === "VERIFIED" || data.verification_mode === "ONCHAIN";
  UI.render(byId("receipt-summary"), [
    candidate.name && UI.card("최종 선택", candidate.name, candidate.category ? `${candidate.category} · 1인 ${UI.money(candidate.price ?? candidate.price_per_person)}` : "최종 결정 결과", "good"),
    UI.card("검증 상태", status === "VERIFIED" ? "모든 증거가 일치합니다" : "영수증 발급 완료", verified ? "내 입력과 최종 기록을 다시 계산해 확인했어요." : "무결성 검증 버튼으로 직접 확인할 수 있어요.", ok ? "good" : ""),
    UI.card("검증 방식", UI.verificationMode(data.verification_mode), data.verification_mode === "ONCHAIN" ? "Sepolia 공개 기록과 비교했습니다." : "로컬 증거를 비교합니다."),
  ]);
}

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
    UI.debug(byId(target), data);
    return data;
  } catch (error) {
    renderFailure(target, error);
    byId(target).textContent = `ERROR\n${error.message}`;
    return null;
  }
}

async function refreshPrivate() {
  const data = await perform(() => request(`/api/demo/participants/${participant}`));
  if (!data) return;
  renderPrivateState(data);
  const proposal = data?.proposal;
  byId("proposal-box").hidden = !proposal || proposal.status !== "PROPOSED";
  if (proposal) {
    byId("proposal-text").textContent = `현재 ${UI.money(proposal.current_constraint_value.amount)} 조건을 ${UI.money(proposal.proposed_constraint_value.amount)}으로 조정하면 모두가 선택할 수 있는 후보 ${proposal.feasible_candidate_count}개가 생겨요.`;
  }
}

async function doJoin(selected, inviteCode) {
  const data = await perform(
    () => request(`/api/demo/participants/${selected}/join`, "POST", { invite_code: inviteCode }),
    "join-output",
  );
  if (!data) return;
  UI.render(byId("join-summary"), [UI.card("참여 완료", `${selected} 참가자 개인 화면`, "이 브라우저에서 내 조건만 안전하게 확인할 수 있어요.", "good")]);
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
    renderDraft(data);
    byId("draft-output").textContent =
      `[${mode} · ${priorityLabel}]\n${data.notice || ""}\n\n` + JSON.stringify(data, null, 2);
  }
};
byId("confirm").onclick = async () => {
  const data = await perform(() => request(`/api/demo/participants/${participant}/constraints/confirm`, "POST", { draft_id: draftId }), "draft-output");
  if (data) { renderDraft(data); byId("confirm").disabled = true; await refreshPrivate(); }
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
const CHAIN_STATUS_LABEL = { CONFIRMED: "기록 완료", PENDING: "기록 대기", FAILED: "기록 실패", UNAVAILABLE: "연결 불가" };

function renderChain(provenance, verifyResult) {
  const box = byId("chain-box");
  const details = byId("chain-details");
  if (!provenance) { details.hidden = true; return; }
  details.hidden = false;

  const status = provenance.status || "UNKNOWN";
  const statusEl = byId("chain-status");
  statusEl.textContent = CHAIN_STATUS_LABEL[status] || "상태 확인";
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
  renderReceipt(latestReceipt);
  byId("receipt-output").textContent = JSON.stringify(latestReceipt, null, 2);
};
byId("verify").onclick = async () => {
  const data = await perform(() => request(`/api/demo/participants/${participant}/verify`, "POST"), "receipt-output");
  if (data) {
    const prov = (latestReceipt && latestReceipt.chain_provenance) || null;
    renderChain(prov, data);
    renderReceipt(data, true);
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
