// SPDX-License-Identifier: MIT
// Guard: the committed widget artifact (spec/assets/openom-badge.js) that gen_site deploys to
// site/widget/ MUST match a fresh, sourcemap-stripped `npm run build:widget`. The widget build is
// deterministic, so a mismatch means the artifact is stale (widget/read source changed without a
// refresh) - which would silently ship an out-of-date /verify/ + <openom-badge> to the live site.
// Fix: `npm --prefix js run build:widget && node js/scripts/refresh-widget-artifact.mjs`.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
for (const name of ["openom-badge.js", "openom-author.js"]) {
  const built = readFileSync(resolve(here, "../widget/dist", name), "utf8").replace(
    /\n\/\/# sourceMappingURL=.*\s*$/,
    "\n",
  );
  const committed = readFileSync(resolve(here, "../../spec/assets", name), "utf8");
  if (built !== committed) {
    console.error(
      `spec/assets/${name} is STALE vs a fresh widget build.\n` +
        "Refresh it: npm --prefix js run build:widget && node js/scripts/refresh-widget-artifact.mjs",
    );
    process.exit(1);
  }
}
console.log("widget artifacts are fresh (match a deterministic build).");
