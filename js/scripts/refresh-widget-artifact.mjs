// SPDX-License-Identifier: MIT
// Copy the freshly-built widget bundle into the committed, deploy-mirrored artifact
// (spec/assets/openom-badge.js), stripping the sourceMappingURL comment so the deployed file
// causes no .map 404. Run after `npm run build:widget` whenever the widget/read source changes.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
for (const name of ["openom-badge.js", "openom-author.js"]) {
  const built = readFileSync(resolve(here, "../widget/dist", name), "utf8").replace(
    /\n\/\/# sourceMappingURL=.*\s*$/,
    "\n",
  );
  const dest = resolve(here, "../../spec/assets", name);
  writeFileSync(dest, built, "utf8");
  console.log(`refreshed ${dest} (${built.length} bytes)`);
}
