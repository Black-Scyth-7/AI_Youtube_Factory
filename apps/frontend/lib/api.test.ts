import { describe, expect, it } from "vitest";

import { API_BASE_PATH } from "@ayf/shared";

describe("api config", () => {
  it("uses the versioned api base path", () => {
    expect(API_BASE_PATH).toBe("/api/v1");
  });
});
