export interface BackendStatus {
  phase: "starting" | "ready" | "failed" | "stopped";
  message: string;
  url?: string;
  recentOutput: string[];
}

const STARTUP_STAGES: ReadonlyArray<readonly [string, number]> = [
  ["CUDA GPU detected", 25],
  ["Attempting to load model", 35],
  ["DiT quantized", 50],
  ["loading 5Hz LM tokenizer", 60],
  ["tokenizer loaded successfully", 72],
  ["Constrained processor initialized", 82],
  ["initialized successfully using PyTorch backend", 90],
  ["Launching server on", 95],
];

export function startupProgress(status: BackendStatus): number {
  if (status.phase === "ready") return 100;
  if (status.phase === "stopped") return 0;

  const output = status.recentOutput.join("\n");
  return STARTUP_STAGES.reduce(
    (progress, [message, stage]) => output.includes(message) ? Math.max(progress, stage) : progress,
    10,
  );
}
