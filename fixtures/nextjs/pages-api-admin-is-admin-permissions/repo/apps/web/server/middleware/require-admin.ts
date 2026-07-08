import type { NextApiRequest, NextApiResponse } from "next";

export async function requireAdmin(req: NextApiRequest, _res: NextApiResponse) {
  const role = req.headers["x-user-role"];
  return role === "ADMIN" ? { role } : null;
}
