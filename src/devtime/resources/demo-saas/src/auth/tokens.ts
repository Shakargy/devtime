import jwt from "jsonwebtoken";

export function issueAccessToken(userId: string): string {
  return jwt.sign({ sub: userId }, process.env.JWT_SECRET as string, {
    expiresIn: "1h",
  });
}

export function verifyAccessToken(token: string): { sub: string } {
  return jwt.verify(token, process.env.JWT_SECRET as string) as { sub: string };
}
