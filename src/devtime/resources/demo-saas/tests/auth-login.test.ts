import { issueAccessToken, verifyAccessToken } from "../src/auth/tokens";

describe("auth login", () => {
  it("issues and verifies a jwt access token", () => {
    process.env.JWT_SECRET = "test-secret";
    const token = issueAccessToken("u_1");
    const payload = verifyAccessToken(token);
    expect(payload.sub).toBe("u_1");
  });
});
