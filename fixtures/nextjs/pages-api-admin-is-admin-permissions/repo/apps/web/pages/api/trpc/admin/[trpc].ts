import type { NextApiRequest, NextApiResponse } from "next";
import { adminRouter } from "../../../../server/routers/admin";
import { requireAdmin } from "../../../../server/middleware/require-admin";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const session = await requireAdmin(req, res);
  if (!session) {
    return res.status(403).json({ error: "admin role required" });
  }
  return adminRouter.handle(req, res);
}
