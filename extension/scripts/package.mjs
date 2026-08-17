// Package the built extension into a Chrome-Web-Store-ready zip ([#104]). Builds dist, then zips the
// CONTENTS of dist/ (manifest.json at the zip root, as the store requires) into
// openom-extension-<version>.zip. A local human step — not CI. Cross-platform (PowerShell on Windows,
// `zip` elsewhere).
import { execSync } from "node:child_process";
import { existsSync, readFileSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const manifest = JSON.parse(readFileSync(join(root, "public", "manifest.json"), "utf8"));
const zipName = `openom-extension-${manifest.version}.zip`;
const zipPath = join(root, zipName);
const dist = join(root, "dist");

console.log("building…");
execSync("node build.mjs", { cwd: root, stdio: "inherit" });
if (existsSync(zipPath)) rmSync(zipPath);

console.log(`zipping dist/ → ${zipName}`);
if (process.platform === "win32") {
  execSync(
    `powershell -NoProfile -Command "Compress-Archive -Path '${dist}\\*' -DestinationPath '${zipPath}' -Force"`,
    { stdio: "inherit" },
  );
} else {
  execSync(`cd "${dist}" && zip -qr "${zipPath}" .`, { stdio: "inherit", shell: "/bin/bash" });
}
console.log(`packaged: ${zipPath}`);
console.log("Upload this zip to the Chrome Web Store, or load dist/ unpacked at chrome://extensions.");
