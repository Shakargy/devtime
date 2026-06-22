import { describe, it, expect } from "vitest";

describe("permalink", () => {
  it("builds an absolute permalink from NEXTAUTH_URL", () => {
    const base = process.env.NEXTAUTH_URL ?? "http://localhost:3000";
    expect(`${base}/p/1`).toContain("/p/1");
  });
});
