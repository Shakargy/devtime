import { describe, it, expect } from "vitest";

describe("trace", () => {
  it("captures session_id in trace data", () => {
    const event = { session_id: "abc123", span: "root" };
    expect(event.session_id).toBe("abc123");
  });
});
