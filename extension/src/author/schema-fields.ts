// Re-export the schema-derived field descriptors from openom-js - the SINGLE source (js/src/fields.ts),
// shared with the hosted authoring companion so the extension form and the web form can never diverge.
export {
  type FieldDescriptor,
  type FieldKind,
  schemaFieldDescriptors,
  humanizeField,
} from "openom-js";
