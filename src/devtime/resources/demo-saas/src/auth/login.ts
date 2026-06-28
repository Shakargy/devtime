import { Router } from "express";
import jwt from "jsonwebtoken";

export const authRouter = Router();

authRouter.post("/auth/login", async (req, res) => {
  const { email, password } = req.body;
  const user = await findUser(email, password);
  if (!user) {
    return res.status(401).json({ error: "invalid_credentials" });
  }
  const token = jwt.sign({ sub: user.id }, process.env.JWT_SECRET as string, {
    expiresIn: "1h",
  });
  return res.json({ token });
});

async function findUser(email: string, password: string) {
  // Lookup omitted for the demo.
  return { id: "u_1", email };
}
