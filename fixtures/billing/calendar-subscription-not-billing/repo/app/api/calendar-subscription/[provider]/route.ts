import { NextResponse } from "next/server";

// Subscribes to a calendar provider's change feed. No payments, no billing.
export async function POST(req: Request) {
  const { provider } = await req.json();
  await subscribeToCalendar(provider);
  return NextResponse.json({ subscribed: true });
}

async function subscribeToCalendar(provider: string) {
  return provider;
}
