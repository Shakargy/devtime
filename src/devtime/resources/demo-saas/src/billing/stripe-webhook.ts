import { Router } from "express";
import Stripe from "stripe";
import { updateSubscriptionState } from "./subscription-service";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY as string);
export const billingRouter = Router();

billingRouter.post("/api/stripe/webhook", async (req, res) => {
  const sig = req.headers["stripe-signature"] as string;
  let event;
  try {
    event = stripe.webhooks.constructEvent(
      (req as any).rawBody,
      sig,
      process.env.STRIPE_WEBHOOK_SECRET as string
    );
  } catch (err) {
    return res.status(400).send("invalid_signature");
  }

  if (event.type === "customer.subscription.updated") {
    await updateSubscriptionState(event.data.object);
  }
  return res.json({ received: true });
});
