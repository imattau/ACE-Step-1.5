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

export async function copyDiagnostics(): Promise<void> {
  const report = await invoke<string>("backend_diagnostics");
  await navigator.clipboard.writeText(report);
}
