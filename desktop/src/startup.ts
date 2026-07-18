import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import { copyDiagnostics, renderStatus, type BackendStatus } from "./diagnostics";
import "./style.css";

const retry = document.querySelector<HTMLButtonElement>("#retry")!;
const openLogs = document.querySelector<HTMLButtonElement>("#open-logs")!;
const diagnostics = document.querySelector<HTMLButtonElement>("#diagnostics")!;
const quit = document.querySelector<HTMLButtonElement>("#quit")!;
const models = document.querySelector<HTMLElement>("#models")!;
const modelSummary = document.querySelector<HTMLParagraphElement>("#model-summary")!;
const lmModel = document.querySelector<HTMLSelectElement>("#lm-model")!;
const installModels = document.querySelector<HTMLButtonElement>("#install-models")!;

interface ModelStatus {
  ready: boolean;
  lmModel: string;
  missing: string[];
  requiredBytes: number;
  freeBytes: number;
}

function formatSize(bytes: number): string {
  return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
}

async function refreshModels(useCurrentChoice = true): Promise<boolean> {
  const arguments_ = useCurrentChoice ? { lmModel: lmModel.value } : {};
  const status = await invoke<ModelStatus>("model_status", arguments_);
  lmModel.value = status.lmModel;
  models.hidden = status.ready;
  if (!status.ready) {
    document.querySelector("#phase")!.textContent = "Models are required before first launch";
    modelSummary.textContent = `Download up to ${formatSize(status.requiredBytes)}. `
      + `${formatSize(status.freeBytes)} is available.`;
  }
  return status.ready;
}

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

lmModel.addEventListener("change", () => refreshModels());
installModels.addEventListener("click", async () => {
  installModels.disabled = true;
  lmModel.disabled = true;
  modelSummary.textContent = "Downloading and verifying models. Interrupted downloads can resume.";
  try {
    await invoke<ModelStatus>("install_models", { lmModel: lmModel.value });
    models.hidden = true;
    await refresh();
  } catch (error) {
    modelSummary.textContent = String(error);
    installModels.disabled = false;
    lmModel.disabled = false;
  }
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

if (await refreshModels(false)) {
  await refresh();
}
