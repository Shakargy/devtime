import { Router } from "express";

export const exportRouter = Router();

exportRouter.get("/api/export/users.csv", async (req, res) => {
  const rows = await loadUsers();
  const csv = rows.map((r) => `${r.id},${r.email}`).join("\n");
  res.setHeader("Content-Type", "text/csv");
  return res.send(csv);
});

async function loadUsers() {
  return [{ id: "u_1", email: "demo@example.com" }];
}
