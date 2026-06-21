import { NextResponse } from "next/server";

export async function POST(req: Request) {
  const event = await req.json();
  if (event.event_type === "BILLING.SUBSCRIPTION.UPDATED") {
    await updateSubscription(event.resource);
  }
  return NextResponse.json({ received: true });
}

async function updateSubscription(resource: any) {
  return resource;
}
