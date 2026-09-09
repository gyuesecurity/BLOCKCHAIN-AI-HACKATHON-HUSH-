const output = document.querySelector("#output");
const status = document.querySelector("#room-status");
const title = document.querySelector("#room-title");

async function refresh() {
  try {
    const response = await fetch("/api/demo/state");
    const state = await response.json();
    title.textContent = state.title;
    status.textContent = state.status;
    output.textContent = JSON.stringify(state, null, 2);
  } catch (error) {
    output.textContent = `ERROR\n${error.message}`;
  }
}

refresh();
setInterval(refresh, 2000);
