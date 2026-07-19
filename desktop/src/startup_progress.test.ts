import assert from "node:assert/strict";
import test from "node:test";

import { startupProgress, type BackendStatus } from "./startup_progress.ts";

function status(phase: BackendStatus["phase"], recentOutput: string[] = []): BackendStatus {
  return { phase, message: "test", recentOutput };
}

test("startup progress advances from backend lifecycle output", () => {
  assert.equal(startupProgress(status("starting")), 10);
  assert.equal(startupProgress(status("starting", ["CUDA GPU detected"])), 25);
  assert.equal(startupProgress(status("starting", ["DiT quantized", "loading 5Hz LM tokenizer"])), 60);
});

test("startup progress completes only when the backend is ready", () => {
  assert.equal(startupProgress(status("starting", ["Launching server on 127.0.0.1"])), 95);
  assert.equal(startupProgress(status("ready")), 100);
});
