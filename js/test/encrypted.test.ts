import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { readPayloadFromBytes } from "../src/read.js";

const fixtures = join(dirname(fileURLToPath(import.meta.url)), "fixtures");

describe("readPayloadFromBytes - encrypted state (#72)", () => {
  test("a user-password PDF that cannot be decrypted reports 'encrypted', not 'absent'", async () => {
    const bytes = new Uint8Array(readFileSync(join(fixtures, "encrypted-userpw.pdf")));
    const r = await readPayloadFromBytes(bytes);
    expect(r.state).toBe("encrypted");
    expect(r.payload).toBeNull();
  });
});
