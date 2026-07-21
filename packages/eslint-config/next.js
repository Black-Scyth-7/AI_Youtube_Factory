// Shared flat ESLint config for Next.js apps.
import base from "./index.js";

/** @type {import("eslint").Linter.Config[]} */
export default [
  ...base,
  {
    rules: {
      // Next.js app-router friendly overrides can be added here.
    },
  },
];
