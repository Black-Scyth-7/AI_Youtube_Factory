import { describe, expect, it } from "vitest";

import { apiUrl, clamp, isNonEmptyString } from "./utils";
import { isEmail, isHttpUrl } from "./validation";

describe("utils", () => {
  it("detects non-empty strings", () => {
    expect(isNonEmptyString("x")).toBe(true);
    expect(isNonEmptyString("  ")).toBe(false);
    expect(isNonEmptyString(1)).toBe(false);
  });

  it("clamps numbers", () => {
    expect(clamp(5, 0, 10)).toBe(5);
    expect(clamp(-1, 0, 10)).toBe(0);
    expect(clamp(99, 0, 10)).toBe(10);
  });

  it("builds api urls without double slashes", () => {
    expect(apiUrl("http://x/", "/health")).toBe("http://x/health");
  });
});

describe("validation", () => {
  it("validates emails", () => {
    expect(isEmail("a@b.com")).toBe(true);
    expect(isEmail("nope")).toBe(false);
  });

  it("validates http urls", () => {
    expect(isHttpUrl("https://example.com")).toBe(true);
    expect(isHttpUrl("ftp://x")).toBe(false);
  });
});
