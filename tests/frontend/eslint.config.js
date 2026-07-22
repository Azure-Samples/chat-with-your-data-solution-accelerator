// Flat ESLint config for the v2 frontend Vitest tree. Mirrors the
// frontend's type-aware preset (`strict-type-checked` +
// `stylistic-type-checked`) but relaxes the mock/test-double rules
// (`no-explicit-any`, `no-unsafe-*`, etc.) that add cost without value in
// the test tier. Type information comes from this package's tsconfig.json,
// which includes the frontend source under test so `@/` imports resolve.

import js from "@eslint/js";
import tseslint from "typescript-eslint";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";

export default tseslint.config(
  {
    ignores: ["node_modules/**", "coverage/**", "**/*.config.js", "**/*.config.ts"],
  },
  js.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,
  {
    files: ["**/*.tsx"],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      globals: {
        ...globals.browser,
        ...globals.es2023,
      },
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      react,
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    settings: {
      react: { version: "detect" },
    },
    rules: {
      ...react.configs.recommended.rules,
      ...react.configs["jsx-runtime"].rules,
      ...reactHooks.configs.recommended.rules,
      // Numbers serialize predictably; this match-everywhere allowance keeps
      // `HTTP ${response.status}` and similar idioms ergonomic without
      // sprinkling `String(...)` calls across every error path.
      "@typescript-eslint/restrict-template-expressions": [
        "error",
        { allowNumber: true },
      ],
      // Mock + test-double affordances: tests routinely use `any` for SDK
      // stubs, empty arrow functions as no-op callbacks, sync `async` for
      // mock signatures, and trivial type-narrowing operators. Tighter
      // rules add cost without value inside the test tier.
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unsafe-assignment": "off",
      "@typescript-eslint/no-unsafe-member-access": "off",
      "@typescript-eslint/no-unsafe-call": "off",
      "@typescript-eslint/no-unsafe-argument": "off",
      "@typescript-eslint/no-unsafe-return": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
      "@typescript-eslint/no-empty-function": "off",
      "@typescript-eslint/require-await": "off",
      "@typescript-eslint/no-confusing-void-expression": "off",
      "@typescript-eslint/no-unnecessary-type-assertion": "off",
      "@typescript-eslint/no-unnecessary-condition": "off",
      "@typescript-eslint/no-base-to-string": "off",
      "@typescript-eslint/consistent-type-definitions": "off",
      "@typescript-eslint/dot-notation": "off",
      "@typescript-eslint/prefer-regexp-exec": "off",
      "@typescript-eslint/array-type": "off",
      "@typescript-eslint/no-unused-vars": "off",
    },
  },
);
