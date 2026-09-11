const output = document.querySelector("#output");
const status = document.querySelector("#room-status");
const title = document.querySelector("#room-title");
const verificationLabel = document.querySelector("#verification-label");
const onchainBox = document.querySelector("#onchain-box");
const onchainSummary = document.querySelector("#onchain-summary");
const onchainLink = document.querySelector("#onchain-link");
const summary = document.querySelector("#shared-summary");
const UI = window.HushUI;

function renderShared(state) {
  const [statusTitle, statusBody] = UI.status(state.status);
  const required = state.required_participant_count || 0;
  const participants = state.participant_count || 0;
  const confirmed = state.input_confirmed_participant_count || 0;
  const cards = [
    UI.card("현재 진행 상태", statusTitle, statusBody, state.status === "COMPLETED" ? "good" : ""),
    UI.card("참여 인원", `${participants} / ${required}명`, participants >= required ? "필요한 참가자가 모두 참여했어요." : `${required - participants}명이 더 참여하면 됩니다.`),
    UI.card("조건 입력 완료", `${confirmed} / ${required}명`, confirmed >= required ? "모든 참가자의 입력이 완료됐어요." : `${required - confirmed}명의 입력을 기다리고 있어요.`),
    UI.card("결과 검증 방식", UI.verificationMode(state.onchain?.status === "CONFIRMED" ? "ONCHAIN" : state.verification_mode), state.onchain?.status === "CONFIRMED" ? "Sepolia 공개 기록과 비교할 수 있어요." : "현재는 서버 내부 증거로 검증합니다."),
  ];
  if (state.final_candidate) cards.unshift(UI.card("최종 선택", state.final_candidate.name || state.final_candidate.candidate_name || "결정 완료", "참가자 모두의 확정된 조건으로 선택됐어요.", "good"));
  UI.render(summary, cards);
}

function renderOnchain(onchain) {
  if (!onchain) {
    onchainBox.hidden = true;
    return;
  }
  onchainBox.hidden = false;
  const tx = onchain.decision_transaction;
  const chainStatus = { CONFIRMED: "기록 완료", PENDING: "기록 대기 중", FAILED: "기록 실패" }[onchain.status] || "상태 확인 중";
  const parts = [`${onchain.network || "테스트넷"} · ${chainStatus}`];
  if (onchain.status === "PENDING") parts.push("(블록 확정 대기 중)");
  if (tx && tx.block_number) parts.push(`block #${tx.block_number}`);
  onchainSummary.textContent = parts.join(" · ");
  const url = (tx && tx.explorer_url) || onchain.explorer_contract_url;
  if (url && onchain.status === "CONFIRMED") {
    onchainLink.hidden = false;
    onchainLink.href = url;
  } else {
    onchainLink.hidden = true;
  }
}

async function refresh() {
  try {
    const response = await fetch("/api/demo/state");
    const state = await response.json();
    title.textContent = state.title;
    status.textContent = UI.status(state.status)[0];
    verificationLabel.textContent = state.onchain?.status === "CONFIRMED"
      ? "Sepolia 블록체인 검증 가능"
      : "로컬 검증 모드";
    renderOnchain(state.onchain);
    renderShared(state);
    UI.debug(output, state);
  } catch (error) {
    UI.render(summary, [UI.card("상태를 불러오지 못했어요", "잠시 후 다시 시도해 주세요", error.message, "warn")]);
    output.textContent = `ERROR\n${error.message}`;
  }
}

refresh();
setInterval(refresh, 2000);
