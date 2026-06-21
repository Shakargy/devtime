import { Router } from "express";
import Stripe from "stripe";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY as string);
export const billingRouter = Router();

billingRouter.post("/api/stripe/webhook", (req, res) => {
  const sig = req.headers["stripe-signature"] as string;
  try {
    stripe.webhooks.constructEvent((req as any).rawBody, sig, process.env.STRIPE_WEBHOOK_SECRET as string);
  } catch {
    return res.status(400).send("invalid_signature");
  }
  return res.json({ received: true });
});
