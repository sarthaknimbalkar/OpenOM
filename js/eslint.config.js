import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["**/dist/**", "node_modules/**", "coverage/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    rules: {
      // The cardinal rule lives in the type system; keep lint strict + focused.
      "@typescript-eslint/no-explicit-any": "error",
      "no-unused-vars": "off", // superseded by the typed rule below
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_", ignoreRestSiblings: true },
      ],
      eqeqeq: ["error", "always"],
      // The XMP packet embeds a mandatory BOM inside a template literal - legitimate.
      "no-irregular-whitespace": ["error", { skipStrings: true, skipTemplates: true }],
    },
  },
  {
    // Node scripts (not part of the TS program) need their runtime globals declared.
    files: ["scripts/**/*.mjs", "**/*.mjs"],
    languageOptions: {
      globals: { process: "readonly", console: "readonly", Buffer: "readonly", URL: "readonly" },
    },
  },
);
