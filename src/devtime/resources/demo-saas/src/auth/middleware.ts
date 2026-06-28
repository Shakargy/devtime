import { Request, Response, NextFunction } from "express";
import { verifyAccessToken } from "./tokens";

export function requireAuth(req: Request, res: Response, next: NextFunction) {
  const header = req.headers.authorization;
  if (!header) {
    return res.status(401).json({ error: "missing_token" });
  }
  try {
    const payload = verifyAccessToken(header.replace("Bearer ", ""));
    (req as any).userId = payload.sub;
    return next();
  } catch {
    return res.status(401).json({ error: "invalid_token" });
  }
}
