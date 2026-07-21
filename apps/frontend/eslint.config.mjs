import nextConfig from "@ayf/eslint-config/next";

export default [
  ...nextConfig,
  {
    ignores: [".next/**", "node_modules/**"],
  },
];
