import { invoke } from "@tauri-apps/api/core";

export interface BackendStatus {
  phase: "starting" | "ready" | "failed" | "stopped";
  message: string;
  url?: string;
  recentOutput: string[];
}

export function renderStatus(status: BackendStatus): void {
  document.querySelector("#phase")!.textContent = status.message;
  const details = document.querySelector<HTMLPreElement>("#details")!;
  details.hidden = status.recentOutput.length === 0;
  details.textContent = status.recentOutput.join("\n");
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
