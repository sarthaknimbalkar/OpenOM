// Defense-in-depth for the author:embed service-worker route ([#98]). The panel already gates embed
// behind validation, but the embed seam must not trust its caller — refuse to embed a schema-invalid
// payload even if something messages author:embed directly. Deterministic; eval-free validator.
import { validatePayload, type PrecompiledValidate } from "openom-js";

export function assertEmbeddable(
  payload: Record<string, unknown>,
  schema: Record<string, unknown>,
  validate: PrecompiledValidate,
): void {
  const report = validatePayload(payload, schema, { validate });
  if (report.errors.length > 0) {
    throw new Error(
      `refusing to embed a schema-invalid payload (${report.errors.map((e) => e.code).join(", ")})`,
    );
  }
}
