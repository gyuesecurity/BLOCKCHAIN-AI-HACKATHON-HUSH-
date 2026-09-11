const page = document.body.dataset.p0Page;
const query = new URLSearchParams(location.search);
const byId = (id) => document.getElementById(id);
const pretty = (value) => JSON.stringify(value, null, 2);
const newKey = () => crypto.randomUUID();

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
    if (session(id)) {
      const me = await api(`/rooms/${encodeURIComponent(id)}/participants/me`, { headers: participantHeaders(id) });
      byId("p0-workspace").hidden = false;
      byId("pseudonym").textContent = `${me.participant_pseudonym} · ${me.input_status}`;
      byId("shared-link").href = `/p0-room?room=${encodeURIComponent(id)}`;
      byId("verify-link").href = `/p0-verify?room=${encodeURIComponent(id)}`;
      const constraints = await api(`/rooms/${encodeURIComponent(id)}/constraints/me`, { headers: participantHeaders(id) });
      show(byId("constraint-output"), constraints);
      const recovery = byId("constraint-recovery"); recovery.replaceChildren();
      for (const item of constraints.constraints.filter((value) => value.commitment_status === "FAILED")) {
        const button = document.createElement("button");
        button.textContent = `${item.constraint_version_id} 온체인 재시도`;
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
    try { show(byId("decision-output"), await api(`/rooms/${id}/decision-runs`, { method: "POST", headers: participantHeaders(id, true) })); await loadParticipantRoom(); }
    catch (error) { show(byId("decision-output"), error.message); }
  };
  byId("retry-final").onclick = async () => {
    const id = roomId();
    try { show(byId("decision-output"), await api(`/rooms/${id}/final-decision/commitment/retry`, { method: "POST", headers: participantHeaders(id, true) })); await loadParticipantRoom(); }
    catch (error) { show(byId("decision-output"), error.message); }
  };
  byId("load-proposals").onclick = async () => {
    const id = roomId(); const list = byId("proposal-list"); list.replaceChildren();
    try {
      const data = await api(`/rooms/${id}/relaxation-proposals/me`, { headers: participantHeaders(id) });
      if (!data.proposals.length) { list.textContent = "현재 내게 온 비공개 협상안이 없습니다."; return; }
      for (const proposal of data.proposals) {
        const card = document.createElement("div"); card.className = "proposal-card";
        const text = document.createElement("p"); text.textContent = pretty(proposal); card.append(text);
        if (proposal.status === "PROPOSED") for (const [decision, label] of [["accept", "완화 수락"], ["reject", "기존 조건 유지"]]) {
          const button = document.createElement("button"); button.textContent = label;
          button.onclick = async () => { try { show(byId("decision-output"), await api(`/rooms/${id}/relaxation-proposals/${proposal.relaxation_proposal_id}/${decision}`, { method: "POST", headers: { ...participantHeaders(id, true), "Content-Type": "application/json" }, body: JSON.stringify({ constraint_version_id: proposal.constraint_version_id }) })); await loadParticipantRoom(); } catch (error) { show(byId("decision-output"), error.message); } };
          card.append(button, document.createTextNode(" "));
        }
        list.append(card);
      }
    } catch (error) { list.textContent = error.message; }
  };
  byId("load-final").onclick = async () => { try { show(byId("receipt-output"), await api(`/rooms/${roomId()}/final-decision`)); } catch (error) { show(byId("receipt-output"), error.message); } };
  byId("load-receipt").onclick = async () => { try { show(byId("receipt-output"), await api(`/rooms/${roomId()}/receipts/me`, { headers: participantHeaders() })); } catch (error) { show(byId("receipt-output"), error.message); } };
  byId("verify-receipt").onclick = async () => { try { show(byId("receipt-output"), await api(`/rooms/${roomId()}/verify`, { method: "POST", headers: participantHeaders() })); } catch (error) { show(byId("receipt-output"), error.message); } };
  await loadParticipantRoom();
}

async function initShared() {
  const id = roomId(); byId("participant-link").href = `/p0?room=${encodeURIComponent(id)}`;
  async function refresh() { try { const data = await api(`/rooms/${encodeURIComponent(id)}`); byId("shared-title").textContent = data.title; byId("shared-status").textContent = data.status; show(byId("shared-output"), data); } catch (error) { show(byId("shared-output"), error.message); } }
  byId("refresh-shared").onclick = refresh; await refresh(); setInterval(refresh, 5000);
}

async function initVerify() {
  const id = roomId(); byId("back-participant").href = `/p0?room=${encodeURIComponent(id)}`; let receipt;
  byId("verify-now").onclick = async () => { try { const result = await api(`/rooms/${id}/verify`, { method: "POST", headers: participantHeaders(id) }); show(byId("verify-output"), result); } catch (error) { show(byId("verify-output"), error.message); } };
  byId("export-receipt").onclick = async () => { try { receipt ||= await api(`/rooms/${id}/verification-data/me`, { headers: participantHeaders(id) }); const blob = new Blob([pretty(receipt)], { type: "application/json" }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `hush-receipt-${id}.json`; link.click(); URL.revokeObjectURL(link.href); } catch (error) { show(byId("verify-output"), error.message); } };
}

if (page === "participant") initParticipant();
if (page === "shared") initShared();
if (page === "verify") initVerify();
