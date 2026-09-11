const page = document.body.dataset.p0Page;
const query = new URLSearchParams(location.search);
const byId = (id) => document.getElementById(id);
const pretty = (value) => JSON.stringify(value, null, 2);
const newKey = () => crypto.randomUUID();
const UI = window.HushUI;

function roomId() { return query.get("room") || byId("room-id")?.value.trim() || ""; }
function sessionKey(id = roomId()) { return `hush:p0:session:${id}`; }
function session(id = roomId()) { return localStorage.getItem(sessionKey(id)); }
function participantHeaders(id = roomId(), mutate = false) {
  const headers = { "X-Participant-Session": session(id) || "" };
  if (mutate) headers["Idempotency-Key"] = newKey();
  return headers;
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  let data;
  try { data = await response.json(); } catch { data = { code: "INVALID_RESPONSE", message: "JSON 응답이 아닙니다." }; }
  if (!response.ok) throw new Error(`${data.code || response.status}: ${data.message || pretty(data)}`);
  return data;
}

function show(target, value) { target.textContent = typeof value === "string" ? value : pretty(value); }
function renderRoom(state) {
  const required = state.required_participant_count || 0;
  const participants = state.participant_count || 0;
  const confirmed = state.input_confirmed_participant_count || 0;
  const [title, body] = UI.status(state.status);
  UI.render(byId("room-summary"), [
    UI.card("현재 진행 상태", title, body, state.status === "COMPLETED" ? "good" : ""),
    UI.card("참여 인원", `${participants} / ${required}명`, participants >= required ? "필요한 참가자가 모두 참여했어요." : `${required - participants}명을 기다리고 있어요.`),
    UI.card("조건 입력 완료", `${confirmed} / ${required}명`, confirmed >= required ? "결정을 실행할 준비가 됐어요." : `${required - confirmed}명의 입력이 남았어요.`),
  ]);
}
function renderConstraints(me, constraints) {
  const own = constraints.constraints || [];
  const active = own.filter((item) => item.status === "ACTIVE");
  const [title, body] = UI.status(me.input_status || me.status);
  UI.render(byId("constraint-summary"), [
    UI.card("내 입력 상태", title, body, me.input_status === "INPUT_CONFIRMED" ? "good" : ""),
    UI.card("현재 사용되는 조건", `${active.length}개`, active.length ? "확정한 조건은 나에게만 상세 표시됩니다." : "조건을 추가하거나 조건 없음으로 완료할 수 있어요."),
    ...active.map((item) => UI.card(`${UI.typeLabel(item.constraint_type)} · ${item.priority === "HARD" ? "필수" : "선호"}`, UI.constraintValue(item.constraint_type, item.constraint_value), `조건 버전 ${item.constraint_version}`)),
  ]);
}
function renderDecision(data) {
  const [title, body] = UI.status(data.decision_status || data.status);
  UI.render(byId("decision-summary"), [
    UI.card("결정 실행 결과", data.status === "FEASIBLE" ? "모두가 선택할 수 있는 장소를 찾았어요" : title, data.status === "FEASIBLE" ? "최종 결과와 검증 영수증을 확인해 주세요." : body, data.status === "FEASIBLE" ? "good" : "warn"),
    data.commitment_status && UI.card("증거 기록", data.commitment_status === "COMMITTED" ? "블록체인 기록 완료" : data.commitment_status === "COMMITTED_LOCALLY" ? "로컬 기록 완료" : "기록 상태 확인 필요", data.commitment_status === "COMMITMENT_FAILED" ? "기록 재시도 버튼을 눌러 주세요." : "결정 증거가 안전하게 저장됐어요."),
  ]);
}
function renderReceipt(data, verified = false) {
  const candidate = data.candidate || data;
  const verifyStatus = data.status;
  UI.render(byId("receipt-summary"), [
    candidate.candidate_name && UI.card("최종 선택", candidate.candidate_name, "확정된 조건으로 선택된 결과입니다.", "good"),
    candidate.name && UI.card("최종 선택", candidate.name, candidate.price ? `${candidate.category} · 1인 ${UI.money(candidate.price)}` : "확정된 조건으로 선택된 결과입니다.", "good"),
    verified && UI.card("검증 결과", verifyStatus === "VERIFIED" ? "모든 증거가 일치합니다" : verifyStatus === "UNAVAILABLE" ? "공개 기록을 잠시 조회할 수 없어요" : "증거가 일치하지 않습니다", data.message || "내 입력과 최종 기록을 다시 계산해 확인했어요.", verifyStatus === "VERIFIED" ? "good" : "warn"),
    data.verification_mode && UI.card("검증 방식", UI.verificationMode(data.verification_mode), data.verification_mode === "ONCHAIN" ? "Sepolia 공개 기록과 비교합니다." : "로컬 증거를 비교합니다."),
  ]);
}
function valueObject(type, raw) {
  if (type === "max_price") return { amount: Number(raw), currency: "KRW" };
  if (type === "max_travel_minutes") return { minutes: Number(raw) };
  if (type === "latest_end_time") return { time: raw.trim() };
  if (type === "excluded_category") return { categories: raw.split(",").map((x) => x.trim()).filter(Boolean) };
  return { features: raw.split(",").map((x) => x.trim()).filter(Boolean) };
}

async function loadParticipantRoom() {
  const id = roomId();
  if (!id) return;
  byId("room-id").value = id;
  try {
    const state = await api(`/rooms/${encodeURIComponent(id)}`);
    show(byId("room-output"), state);
    renderRoom(state);
    if (session(id)) {
      const me = await api(`/rooms/${encodeURIComponent(id)}/participants/me`, { headers: participantHeaders(id) });
      byId("p0-workspace").hidden = false;
      byId("pseudonym").textContent = `참가자 ${me.participant_pseudonym} · ${UI.status(me.input_status)[0]}`;
      byId("shared-link").href = `/p0-room?room=${encodeURIComponent(id)}`;
      byId("verify-link").href = `/p0-verify?room=${encodeURIComponent(id)}`;
      const constraints = await api(`/rooms/${encodeURIComponent(id)}/constraints/me`, { headers: participantHeaders(id) });
      show(byId("constraint-output"), constraints);
      renderConstraints(me, constraints);
      const recovery = byId("constraint-recovery"); recovery.replaceChildren();
      for (const item of constraints.constraints.filter((value) => value.commitment_status === "FAILED")) {
        const button = document.createElement("button");
        button.textContent = "조건의 블록체인 기록 다시 시도";
        button.onclick = async () => {
          try { show(byId("constraint-output"), await api(`/rooms/${id}/constraints/${item.constraint_version_id}/commitments/retry`, { method: "POST", headers: participantHeaders(id, true) })); await loadParticipantRoom(); }
          catch (error) { show(byId("constraint-output"), error.message); }
        };
        recovery.append(button);
      }
    }
  } catch (error) { show(byId("room-output"), error.message); }
}

async function initParticipant() {
  const token = query.get("token");
  if (query.get("room")) byId("room-id").value = query.get("room");
  if (token) byId("invite-token").value = token;
  byId("create-room").onclick = async () => {
    try {
      const data = await api("/rooms", {
        method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": newKey() },
        body: JSON.stringify({ title: byId("title").value, required_participant_count: Number(byId("required-count").value), candidate_dataset_version: "demo-candidates-v1" }),
      });
      byId("room-id").value = data.decision_room_id;
      byId("invite-token").value = data.invite_token;
      history.replaceState(null, "", `/p0?room=${encodeURIComponent(data.decision_room_id)}&token=${encodeURIComponent(data.invite_token)}`);
      show(byId("room-output"), { ...data, invite_url: `${location.origin}/p0?room=${data.decision_room_id}&token=${data.invite_token}` });
      UI.render(byId("room-summary"), [UI.card("새 의사결정 방", "방을 만들었어요", "초대 링크를 팀원에게 전달하고, 만든 사람도 아래에서 참가해 주세요.", "good")]);
    } catch (error) { show(byId("room-output"), error.message); }
  };
  byId("join-room").onclick = async () => {
    const id = byId("room-id").value.trim();
    try {
      const data = await api(`/rooms/${encodeURIComponent(id)}/participants`, {
        method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": newKey() },
        body: JSON.stringify({ invite_token: byId("invite-token").value.trim() }),
      });
      localStorage.setItem(sessionKey(id), data.participant_session);
      history.replaceState(null, "", `/p0?room=${encodeURIComponent(id)}`);
      await loadParticipantRoom();
    } catch (error) { show(byId("room-output"), error.message); }
  };
  byId("refresh-room").onclick = loadParticipantRoom;
  byId("parse-input").onclick = async () => {
    const id = roomId();
    try {
      const received = await api(`/rooms/${id}/private-inputs`, { method: "POST", headers: { ...participantHeaders(id, true), "Content-Type": "application/json" }, body: JSON.stringify({ source_text: byId("source-text").value }) });
      const parsed = await api(`/rooms/${id}/private-inputs/${received.private_input_id}/parse`, { method: "POST", headers: participantHeaders(id, true) });
      const candidate = parsed.structured_candidates[0];
      byId("constraint-type").value = candidate.constraint_type;
      byId("priority").value = candidate.priority;
      const value = candidate.constraint_value;
      byId("constraint-value").value = value.amount ?? value.minutes ?? value.time ?? (value.categories || value.features || []).join(",");
      show(byId("constraint-output"), parsed);
      UI.render(byId("constraint-summary"), [
        UI.card("해석 방식", parsed.is_ai ? `AI · ${parsed.model || "LLM"}` : "규칙 기반 구조화", parsed.notice),
        UI.card(`${UI.typeLabel(candidate.constraint_type)} · ${candidate.priority === "HARD" ? "필수" : "선호"}`, UI.constraintValue(candidate.constraint_type, candidate.constraint_value), "내용을 확인한 뒤 조건 확정을 눌러 주세요.", "good"),
      ]);
    } catch (error) { show(byId("constraint-output"), error.message); }
  };
  byId("add-constraint").onclick = async () => {
    const id = roomId(); const type = byId("constraint-type").value;
    try {
      const data = await api(`/rooms/${id}/constraints`, { method: "POST", headers: { ...participantHeaders(id, true), "Content-Type": "application/json" }, body: JSON.stringify({ constraint_type: type, priority: byId("priority").value, constraint_value: valueObject(type, byId("constraint-value").value), source_text: byId("source-text").value || null }) });
      show(byId("constraint-output"), data); await loadParticipantRoom();
    } catch (error) { show(byId("constraint-output"), error.message); }
  };
  async function confirm(mode) {
    const id = roomId();
    try { const data = await api(`/rooms/${id}/input-confirmations`, { method: "POST", headers: { ...participantHeaders(id, true), "Content-Type": "application/json" }, body: JSON.stringify({ input_mode: mode }) }); show(byId("constraint-output"), data); await loadParticipantRoom(); }
    catch (error) { show(byId("constraint-output"), error.message); }
  }
  byId("confirm-constrained").onclick = () => confirm("CONSTRAINED");
  byId("confirm-empty").onclick = () => confirm("EMPTY");
  byId("run-decision").onclick = async () => {
    const id = roomId();
    try { const data = await api(`/rooms/${id}/decision-runs`, { method: "POST", headers: participantHeaders(id, true) }); show(byId("decision-output"), data); renderDecision(data); await loadParticipantRoom(); }
    catch (error) { show(byId("decision-output"), error.message); }
  };
  byId("retry-final").onclick = async () => {
    const id = roomId();
    try { const data = await api(`/rooms/${id}/final-decision/commitment/retry`, { method: "POST", headers: participantHeaders(id, true) }); show(byId("decision-output"), data); renderDecision(data); await loadParticipantRoom(); }
    catch (error) { show(byId("decision-output"), error.message); }
  };
  byId("load-proposals").onclick = async () => {
    const id = roomId(); const list = byId("proposal-list"); list.replaceChildren();
    try {
      const data = await api(`/rooms/${id}/relaxation-proposals/me`, { headers: participantHeaders(id) });
      if (!data.proposals.length) { list.textContent = "현재 내게 온 비공개 협상안이 없습니다."; return; }
      for (const proposal of data.proposals) {
        const card = document.createElement("div"); card.className = "proposal-card";
        const heading = document.createElement("h3"); heading.textContent = "내 조건을 조금 조정하면 합의할 수 있어요";
        const text = document.createElement("p"); text.textContent = `${UI.typeLabel(proposal.constraint_type)}: ${UI.constraintValue(proposal.constraint_type, proposal.current_constraint_value)} → ${UI.constraintValue(proposal.constraint_type, proposal.proposed_constraint_value)} · 가능한 후보 ${proposal.feasible_candidate_count}개`;
        card.append(heading, text);
        if (proposal.status === "PROPOSED") for (const [decision, label] of [["accept", "완화 수락"], ["reject", "기존 조건 유지"]]) {
          const button = document.createElement("button"); button.textContent = label;
          button.onclick = async () => { try { show(byId("decision-output"), await api(`/rooms/${id}/relaxation-proposals/${proposal.relaxation_proposal_id}/${decision}`, { method: "POST", headers: { ...participantHeaders(id, true), "Content-Type": "application/json" }, body: JSON.stringify({ constraint_version_id: proposal.constraint_version_id }) })); await loadParticipantRoom(); } catch (error) { show(byId("decision-output"), error.message); } };
          card.append(button, document.createTextNode(" "));
        }
        list.append(card);
      }
    } catch (error) { list.textContent = error.message; }
  };
  byId("load-final").onclick = async () => { try { const data = await api(`/rooms/${roomId()}/final-decision`); show(byId("receipt-output"), data); renderReceipt(data); } catch (error) { show(byId("receipt-output"), error.message); } };
  byId("load-receipt").onclick = async () => { try { const data = await api(`/rooms/${roomId()}/receipts/me`, { headers: participantHeaders() }); show(byId("receipt-output"), data); renderReceipt(data); } catch (error) { show(byId("receipt-output"), error.message); } };
  byId("verify-receipt").onclick = async () => { try { const data = await api(`/rooms/${roomId()}/verify`, { method: "POST", headers: participantHeaders() }); show(byId("receipt-output"), data); renderReceipt(data, true); } catch (error) { show(byId("receipt-output"), error.message); } };
  await loadParticipantRoom();
}

async function initShared() {
  const id = roomId(); byId("participant-link").href = `/p0?room=${encodeURIComponent(id)}`;
  async function refresh() { try { const data = await api(`/rooms/${encodeURIComponent(id)}`); const [title, body] = UI.status(data.status); byId("shared-title").textContent = data.title; byId("shared-status").textContent = title; UI.render(byId("shared-summary"), [UI.card("현재 진행 상태", title, body, data.status === "COMPLETED" ? "good" : ""), UI.card("참여 인원", `${data.participant_count} / ${data.required_participant_count}명`, "개인 조건은 공용 화면에 표시되지 않습니다."), UI.card("조건 입력 완료", `${data.input_confirmed_participant_count} / ${data.required_participant_count}명`, data.input_confirmed_participant_count === data.required_participant_count ? "모든 입력이 완료됐어요." : "나머지 참가자의 입력을 기다리고 있어요."), data.final_decision && UI.card("최종 선택", data.final_decision.candidate_name, "결정이 완료됐어요.", "good")]); show(byId("shared-output"), data); } catch (error) { UI.render(byId("shared-summary"), [UI.card("상태를 불러오지 못했어요", "다시 시도해 주세요", error.message, "warn")]); show(byId("shared-output"), error.message); } }
  byId("refresh-shared").onclick = refresh; await refresh(); setInterval(refresh, 5000);
}

async function initVerify() {
  const id = roomId(); byId("back-participant").href = `/p0?room=${encodeURIComponent(id)}`; let receipt;
  byId("verify-now").onclick = async () => { try { const result = await api(`/rooms/${id}/verify`, { method: "POST", headers: participantHeaders(id) }); const checks = Object.values(result.checks || {}); const passed = checks.filter(Boolean).length; UI.render(byId("verify-summary"), [UI.card("검증 결과", result.status === "VERIFIED" ? "모든 증거가 일치합니다" : result.status === "UNAVAILABLE" ? "공개 기록을 잠시 조회할 수 없어요" : "일치하지 않는 증거가 있습니다", result.message || `${passed} / ${checks.length}개 검증 항목 확인`, result.status === "VERIFIED" ? "good" : "warn"), UI.card("검증 방식", UI.verificationMode(result.verification_mode), result.verification_mode === "ONCHAIN" ? "Sepolia 공개 기록까지 비교했습니다." : "로컬 증거를 비교했습니다.")]); show(byId("verify-output"), result); } catch (error) { UI.render(byId("verify-summary"), [UI.card("검증하지 못했어요", "참가자 세션을 확인해 주세요", error.message, "warn")]); show(byId("verify-output"), error.message); } };
  byId("export-receipt").onclick = async () => { try { receipt ||= await api(`/rooms/${id}/verification-data/me`, { headers: participantHeaders(id) }); const blob = new Blob([pretty(receipt)], { type: "application/json" }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `hush-receipt-${id}.json`; link.click(); URL.revokeObjectURL(link.href); } catch (error) { show(byId("verify-output"), error.message); } };
}

if (page === "participant") initParticipant();
if (page === "shared") initShared();
if (page === "verify") initVerify();
