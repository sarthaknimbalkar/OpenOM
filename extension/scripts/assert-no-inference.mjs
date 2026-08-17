#!/usr/bin/env node
// Fail if any inference/model client leaked into the built consumer bundle ([OM-DoD-006], §6a
// cardinal rule). Scans dist/**/*.js for known SDK names as whole words. Usage:
//   node scripts/assert-no-inference.mjs [distDir=dist]

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const dist = process.argv[2] ?? "dist";
const FORBIDDEN =
  /\b(openai|anthropic|cohere|langchain|llama[_-]?index|transformers|tensorflow|onnxruntime|sentence-transformers|@google\/generative-ai|replicate)\b/i;

function jsFiles(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...jsFiles(p));
    else if (name.endsWith(".js")) out.push(p);
  }
  return out;
}

let leaked = false;
for (const file of jsFiles(dist)) {
  const m = FORBIDDEN.exec(readFileSync(file, "utf8"));
  if (m) {
    console.error(`::error:: inference client "${m[0]}" found in consumer bundle: ${file}`);
    leaked = true;
  }
}

if (leaked) {
  console.error("assert-no-inference FAILED — the consumer bundle must be inference-free (§6a).");
  process.exit(1);
}
console.log(`assert-no-inference OK — ${dist} is inference-free.`);
