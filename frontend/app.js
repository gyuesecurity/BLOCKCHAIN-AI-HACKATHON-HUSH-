const output = document.querySelector("#output");
const status = document.querySelector("#room-status");
const title = document.querySelector("#room-title");
const verificationLabel = document.querySelector("#verification-label");
const onchainBox = document.querySelector("#onchain-box");
const onchainSummary = document.querySelector("#onchain-summary");
const onchainLink = document.querySelector("#onchain-link");

function renderOnchain(onchain) {
  if (!onchain) {
    onchainBox.hidden = true;
    return;
  }
  onchainBox.hidden = false;
  const tx = onchain.decision_transaction;
  const parts = [`${onchain.network || "testnet"} · ${onchain.status}`];
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
    status.textContent = state.status;
    if (state.verification_label) verificationLabel.textContent = state.verification_label;
    renderOnchain(state.onchain);
    output.textContent = JSON.stringify(state, null, 2);
  } catch (error) {
    output.textContent = `ERROR\n${error.message}`;
  }
}

refresh();
setInterval(refresh, 2000);
