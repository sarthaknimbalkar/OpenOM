import { describe, expect, test } from "vitest";
import schema from "../../../spec/om-0.1.schema.json";
import { schemaFieldDescriptors } from "../../src/author/schema-fields.js";

describe("schemaFieldDescriptors (#77/#93)", () => {
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
});
