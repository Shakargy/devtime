import { NextResponse } from "next/server";
import Stripe from "stripe";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY as string);

export async function POST(req: Request) {
  const sig = req.headers.get("stripe-signature") as string;
  try {
    stripe.webhooks.constructEvent(
      await req.text(),
      sig,
      process.env.STRIPE_WEBHOOK_SECRET as string
    );
  } catch {
    return new NextResponse("invalid_signature", { status: 400 });
  }
  return NextResponse.json({ received: true });
}
