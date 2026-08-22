import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, test } from "vitest";
import {
  validateSubscription,
  SUBSCRIPTION_SCHEMA,
  SUBSCRIPTION_EVENTS,
} from "../src/subscription.js";

const specDir = join(__dirname, "..", "..", "spec");

const valid = {
  subscriptionVersion: "1",
  specVersion: "0.1",
  receiverUrl: "https://portal.example.com/hooks/openom",
  secret: "a-strong-shared-secret-1234",
  events: ["om.payload.published"],
  active: true,
};

describe("validateSubscription ([B2] §Y subscription object)", () => {
  test("accepts a well-formed subscription", () => {
    expect(validateSubscription(valid)).toEqual({ valid: true, errors: [] });
  });

  test("events is optional (absent = deliver all)", () => {
    const { events, ...noEvents } = valid;
    void events;
    expect(validateSubscription(noEvents).valid).toBe(true);
  });

  test("rejects a non-https receiver (no plaintext delivery)", () => {
    const r = validateSubscription({ ...valid, receiverUrl: "http://portal.example.com/h" });
    expect(r.valid).toBe(false);
  });

  test("rejects a too-short secret", () => {
    expect(validateSubscription({ ...valid, secret: "short" }).valid).toBe(false);
  });

  test("rejects an unknown event in the filter", () => {
    expect(validateSubscription({ ...valid, events: ["om.bogus"] }).valid).toBe(false);
  });

  test("rejects unknown top-level properties", () => {
    expect(validateSubscription({ ...valid, extra: 1 }).valid).toBe(false);
  });

  test("event enum lists only events the tooling actually emits ([#3])", () => {
    expect(SUBSCRIPTION_EVENTS).toContain("om.payload.published");
    expect(SUBSCRIPTION_EVENTS).toContain("om.test.ping");
    expect(SUBSCRIPTION_EVENTS).not.toContain("om.payload.superseded"); // not emitted yet
  });

  test("SUBSCRIPTION_SCHEMA equals the published spec/webhook-subscription-0.1.schema.json", () => {
    const published = JSON.parse(
      readFileSync(join(specDir, "webhook-subscription-0.1.schema.json"), "utf8"),
    );
    expect(published).toEqual(JSON.parse(JSON.stringify(SUBSCRIPTION_SCHEMA)));
  });
});
