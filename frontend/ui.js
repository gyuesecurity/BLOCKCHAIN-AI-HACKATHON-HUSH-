(function () {
  const STATUS = {
    OPEN: ["참가자 모집 중", "초대받은 참가자가 방에 들어오기를 기다리고 있어요."],
    COLLECTING: ["조건 입력 중", "참가자들이 각자의 비공개 조건을 입력하고 있어요."],
    READY: ["결정 준비 완료", "모든 참가자의 입력이 완료됐어요. 이제 결정을 실행할 수 있습니다."],
    DECIDING: ["결정 계산 중", "확정된 조건으로 가능한 선택지를 계산하고 있어요."],
    NEGOTIATING: ["비공개 조건 조율 중", "한 참가자에게만 조건 조정 제안이 전달됐어요."],
    FINALIZING: ["블록체인 기록 중", "최종 결과를 블록체인에 안전하게 기록하고 있어요."],
    COMPLETED: ["최종 결정 완료", "모든 절차가 완료됐어요. 참가자는 영수증을 검증할 수 있습니다."],
    CLOSED: ["결정 종료", "현재 조건으로 합의할 수 없어 방이 종료됐어요."],
    JOINED: ["방 참여 완료", "조건 입력을 기다리고 있어요."],
    ACTIVE: ["조건 제출 완료", "내 조건이 이번 결정에 반영될 준비가 됐어요."],
    RECEIPT_AVAILABLE: ["영수증 발급 완료", "내 입력이 반영됐는지 검증할 수 있어요."],
    PENDING_INPUT: ["조건 입력 대기", "아직 조건 입력을 완료하지 않았어요."],
    INPUT_CONFIRMED: ["조건 입력 완료", "내 입력이 안전하게 확정됐어요."],
  };
  const TYPES = {
    max_price: "최대 가격",
    max_travel_minutes: "최대 이동 시간",
    latest_end_time: "최종 종료 시간",
    excluded_category: "제외 음식",
    accessibility_required: "필수 접근성",
  };

  function status(value) { return STATUS[value] || [value || "상태 확인 중", "현재 상태를 확인하고 있어요."]; }
  function money(value) { return `${Number(value).toLocaleString("ko-KR")}원`; }
  function constraintValue(type, value = {}) {
    if (type === "max_price") return money(value.amount);
    if (type === "max_travel_minutes") return `${value.minutes}분 이내`;
    if (type === "latest_end_time") return `${value.time}까지`;
    if (type === "excluded_category") return `${(value.categories || []).join(", ")} 제외`;
    if (type === "accessibility_required") return `${(value.features || []).join(", ")} 필요`;
    return "확정된 조건";
  }
  function card(title, value, body, tone = "") { return { title, value, body, tone }; }
  function render(target, cards) {
    target.replaceChildren();
    for (const item of cards.filter(Boolean)) {
      const article = document.createElement("article");
      article.className = `summary-item ${item.tone || ""}`.trim();
      const label = document.createElement("span"); label.className = "summary-label"; label.textContent = item.title;
      const value = document.createElement("strong"); value.className = "summary-value"; value.textContent = item.value;
      article.append(label, value);
      if (item.body) { const body = document.createElement("p"); body.textContent = item.body; article.append(body); }
      target.append(article);
    }
  }
  function debug(pre, value) { pre.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2); }
  function verificationMode(mode) { return mode === "ONCHAIN" ? "블록체인 검증" : "로컬 검증"; }

  window.HushUI = { status, money, constraintValue, typeLabel: (type) => TYPES[type] || type, card, render, debug, verificationMode };
})();
