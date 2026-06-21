import { NextResponse } from "next/server";

// A generic inbound webhook receiver and delivery log. No billing, no Stripe,
// no subscriptions, no signature verification.
export async function POST(req: Request) {
  const payload = await req.json();
  await recordDelivery(payload);
  return NextResponse.json({ stored: true });
}

export async function GET() {
  return NextResponse.json(await listDeliveries());
}

async function recordDelivery(payload: unknown) {
  return payload;
}
async function listDeliveries() {
  return [];
}
