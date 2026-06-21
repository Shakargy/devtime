import { NextResponse } from "next/server";

// Generic inbound webhook receiver. No billing/payment logic in this handler.
export async function POST(req: Request) {
  const payload = await req.json();
  await recordDelivery(payload);
  return NextResponse.json({ stored: true });
}

async function recordDelivery(payload: unknown) {
  return payload;
}
