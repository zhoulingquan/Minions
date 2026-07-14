import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        {
          allowConstantExport: true,
          allowExportNames: [
            "ACPRedirect",
            "BUILTIN_ROUTES",
            "DefaultRedirect",
            "SOURCE_LABELS",
            "getFileIcon",
            "getSkillVisual",
            "mermaidComponents",
            "normalizeLevel",
            "parseArgsText",
            "parseEnvText",
            "parseFrontmatter",
            "sourceLabel",
            "stringifyArgs",
            "stringifyEnv",
            "useApprovalContext",
            "useContextMenu",
            "usePlugins",
            "useTheme",
          ],
        },
      ],
    },
  },
  {
    files: [
      "src/components/MermaidCodeBlock/mermaidComponents.tsx",
      "src/layouts/registry/builtinRoutes.tsx",
    ],
    rules: {
      // These modules intentionally export component registries rather than
      // renderable component entry points, so Fast Refresh cannot track them.
      "react-refresh/only-export-components": "off",
    },
  },
  {
    files: [
      "**/*.test.{ts,tsx}",
      "**/__tests__/**/*.{ts,tsx}",
      "src/test/**/*.{ts,tsx}",
    ],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-require-imports": "off",
      "react-refresh/only-export-components": "off",
    },
  },
);
