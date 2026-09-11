const grid = document.getElementById("invite-grid");
const hint = document.getElementById("invite-hint");

async function load() {
  try {
    const res = await fetch("/api/demo/invites");
    const data = await res.json();
    grid.innerHTML = "";
    for (const p of data.participants) {
      const card = document.createElement("div");
      card.className = "invite-card";
      const img = document.createElement("img");
      img.alt = `참가자 ${p.participant} 초대 QR`;
      img.loading = "lazy";
      img.src = `/api/demo/invite-qr/${p.participant}`;
      const link = document.createElement("a");
      link.href = p.join_url;
      link.textContent = "링크로 열기";
      const heading = document.createElement("h3");
      heading.textContent = `참가자 ${p.participant}`;
      const codeEl = document.createElement("code");
      codeEl.textContent = p.invite_code;
      card.append(heading, img, link, codeEl);
      grid.appendChild(card);
    }
    hint.textContent = `이 페이지 주소: ${location.origin}/invite · 초대 코드는 시연용 fixture입니다.`;
  } catch (error) {
    grid.textContent = `초대 정보를 불러오지 못했습니다: ${error.message}`;
  }
}

load();
