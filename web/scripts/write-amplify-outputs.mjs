#!/usr/bin/env node
// Writes web/amplify_outputs.json from AMPLIFY_OUTPUTS_JSON at build time.
// The file is generated (and gitignored) so CSP/auth config never enters the repo.
import { writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const raw = process.env.AMPLIFY_OUTPUTS_JSON;

if (!raw || raw.trim() === "") {
  console.error(
    "[write-amplify-outputs] AMPLIFY_OUTPUTS_JSON is missing or empty.\n" +
      "Set it to the Amplify Gen2 outputs JSON before building, e.g.\n" +
      '  AMPLIFY_OUTPUTS_JSON="$(cat amplify_outputs.json)" pnpm build',
  );
  process.exit(1);
}

let outputs;
try {
  outputs = JSON.parse(raw);
} catch (error) {
  console.error(
    `[write-amplify-outputs] AMPLIFY_OUTPUTS_JSON is not valid JSON: ${error.message}`,
  );
  process.exit(1);
}

if (typeof outputs !== "object" || outputs === null || Array.isArray(outputs)) {
  console.error(
    "[write-amplify-outputs] AMPLIFY_OUTPUTS_JSON must be a JSON object.",
  );
  process.exit(1);
}

const outputPath = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "amplify_outputs.json",
);

writeFileSync(outputPath, `${JSON.stringify(outputs, null, 2)}\n`, "utf8");
console.log(`[write-amplify-outputs] wrote ${outputPath}`);
