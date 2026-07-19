import { invoke } from "@tauri-apps/api/core";

import { startupProgress, type BackendStatus } from "./startup_progress";

export type { BackendStatus } from "./startup_progress";

export function renderStatus(status: BackendStatus): void {
  document.querySelector("#phase")!.textContent = status.message;
  const progress = document.querySelector<HTMLProgressElement>("#progress")!;
  const progressLabel = document.querySelector<HTMLSpanElement>("#progress-label")!;
  const progressGroup = document.querySelector<HTMLElement>("#startup-progress")!;
  const value = startupProgress(status);
  progress.value = value;
  progressLabel.textContent = `${value}%`;
  progressGroup.hidden = status.phase === "failed";
}

export async function fetchDiagnostics(): Promise<string> {
  return invoke<string>("backend_diagnostics");
}

export async function copyDiagnostics(): Promise<void> {
  const report = await fetchDiagnostics();
  await navigator.clipboard.writeText(report);
}

export async function showDiagnostics(): Promise<void> {
  const report = await fetchDiagnostics();
  const details = document.querySelector<HTMLPreElement>("#details")!;
  details.hidden = false;
  details.textContent = report;
}
