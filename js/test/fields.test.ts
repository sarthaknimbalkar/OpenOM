import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, test } from "vitest";
import { schemaFieldDescriptors, humanizeField } from "../src/fields.js";

const specDir = join(__dirname, "..", "..", "spec");
const schema = JSON.parse(readFileSync(join(specDir, "om-0.1.schema.json"), "utf8"));

describe("schemaFieldDescriptors (#77/#93) - single source shared by extension + web companion", () => {
  const d = schemaFieldDescriptors(schema as { properties?: Record<string, unknown> });
  const by = (p: string) => d.find((f) => f.path === p);

  test("types each field from the schema", () => {
    expect(by("/deal/noiType")).toMatchObject({ kind: "enum", enum: ["in-place", "pro-forma"] });
    expect(by("/deal/noiAsOfDate")?.kind).toBe("date");
    expect(by("/deal/askingPrice")?.kind).toBe("number");
    expect(by("/lease/landlordResponsibilities/roof")?.kind).toBe("boolean");
    expect(by("/property/address/streetAddress")?.kind).toBe("text");
  });

  test("covers the field map and humanizes labels", () => {
    expect(d.length).toBeGreaterThan(20);
    expect(by("/deal/capRate")?.label.toLowerCase()).toContain("cap");
  });

  test("excludes array nodes (rentSchedule/options handled specially)", () => {
    expect(d.some((f) => f.path.startsWith("/lease/rentSchedule"))).toBe(false);
    expect(d.some((f) => f.path === "/lease/options")).toBe(false);
  });

  test("humanizeField splits camelCase and capitalizes", () => {
    expect(humanizeField("/deal/noiAsOfDate")).toBe("Noi As Of Date");
    expect(humanizeField("/deal/capRate")).toBe("Cap Rate");
  });
});
