import { defineConfig } from "vitest/config";

export default defineConfig({
  define: { __DEV__: "false" },
  test: { include: ["tests/unit/**/*.test.ts"], environment: "node" },
});
