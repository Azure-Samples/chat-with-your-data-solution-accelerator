// Flat ESLint config for the v2 frontend. Pairs the
// `@typescript-eslint/strict-type-checked` + `stylistic-type-checked`
// presets (the type-aware ruleset that mirrors backend `pyright --strict`
// posture) with the React + react-hooks + react-refresh plugins, scoped
// per ADR 0013 to `.tsx`-only files. Type information is supplied via
// `projectService: true`, which reads `tsconfig.json` automatically.
//
// Scoped to `src/**`. The frontend Vitest tree is a separate workspace
// member (tests/frontend) and carries its own ESLint config.

import js from "@eslint/js";
import tseslint from "typescript-eslint";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";

export default tseslint.config(
  {
    ignores: ["dist/**", "node_modules/**", "coverage/**", "**/*.config.js", "**/*.config.ts"],
  },
  js.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,
  {
    files: ["src/**/*.tsx"],
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
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
      // Numbers serialize predictably; this match-everywhere allowance keeps
      // `HTTP ${response.status}` and similar idioms ergonomic without
      // sprinkling `String(...)` calls across every error path.
      "@typescript-eslint/restrict-template-expressions": [
        "error",
        { allowNumber: true },
      ],
      // Cross-folder imports must go through the `@/*` alias (ADR 0015).
      // Regex matches the source text only -- sibling `./X` passes; the
      // resolved-path check that `import/no-relative-parent-imports`
      // would do is the wrong shape here (it would flag aliased
      // `@/pages/...` because the resolver maps it to a parent dir).
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              regex: "^\\.\\./",
              message: "Cross-folder imports must use the '@/' path alias (see ADR 0015). Sibling './X' imports are allowed.",
            },
          ],
        },
      ],
    },
  },
);
