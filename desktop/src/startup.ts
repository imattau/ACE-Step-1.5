import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import { copyDiagnostics, renderStatus, type BackendStatus } from "./diagnostics";
import "./style.css";

const retry = document.querySelector<HTMLButtonElement>("#retry")!;
const openLogs = document.querySelector<HTMLButtonElement>("#open-logs")!;
const diagnostics = document.querySelector<HTMLButtonElement>("#diagnostics")!;
const quit = document.querySelector<HTMLButtonElement>("#quit")!;

async function refresh(): Promise<void> {
  const status = await invoke<BackendStatus>("backend_status");
  renderStatus(status);
  retry.hidden = status.phase !== "failed";
  if (status.phase === "ready" && status.url) {
    window.location.replace(status.url);
  }
}

retry.addEventListener("click", async () => {
  retry.hidden = true;
  await invoke("retry_backend");
  await refresh();
});

diagnostics.addEventListener("click", () => copyDiagnostics());
openLogs.addEventListener("click", () => invoke("open_logs"));
quit.addEventListener("click", () => invoke("quit_app"));

await listen<BackendStatus>("backend-status", ({ payload }) => {
  renderStatus(payload);
  retry.hidden = payload.phase !== "failed";
  if (payload.phase === "ready" && payload.url) {
    window.location.replace(payload.url);
  }
});

await refresh();
