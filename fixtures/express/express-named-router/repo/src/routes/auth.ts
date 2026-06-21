import { Router } from "express";
import jwt from "jsonwebtoken";

export const authRouter = Router();

authRouter.post("/auth/login", (req, res) => {
  const token = jwt.sign({ sub: "u_1" }, process.env.JWT_SECRET as string);
  return res.json({ token });
});
